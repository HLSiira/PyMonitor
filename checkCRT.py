#!/usr/bin/env python3

##############################################################################80
# Certbot Automated Renew 20231226
##############################################################################80
# Description: This script uses Certbot to renew SSL certificates and sends a
# notification about the renewal status. Requires root privileges
# Usage via CRON: (Runs every day at 0702, must be ROOT user)
#   2 7 * * * cd /path/to/folder && ./checkCRT.py --cron 2>&1 | ./tailog.py
# Usage via CLI:
#   cd /path/to/folder && ./checkCRT.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import subprocess
import os, re, sys
from datetime import datetime, timedelta
import csv
from collections import namedtuple
from utils import checkSudo, cPrint, getBaseParser, pingHealth, sendNotification

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser(
    "Leverages Certbot to request, renew, or revoke SSL Certs. Requires root."
)
args = parser.parse_args()
datapath = "data/domains.csv"
dateFormat = "%Y%m%d"
availableConfigs = "/etc/apache2/sites-available/"
enabledConfigs = "/etc/apache2/sites-enabled"
TN00 = datetime.now()  # Now
TM30 = datetime.now() - timedelta(days=30)  # 30 days ago
TP30 = datetime.now() + timedelta(days=30)  # 30 days from now
TP90 = datetime.now() + timedelta(days=90)  # 90 days from now

Config = namedtuple("Config", ["domain", "status", "lastSeen", "expires"])


##############################################################################80
# Function to load device database from CSV
##############################################################################80
def loadDatabase(filepath):
    cPrint("Reading device database...", "BLUE") if args.debug else None
    database = {}
    if not os.path.exists(filepath):
        return database

    with open(filepath, mode="r") as reader:
        # Create a DictReader, and then strip whitespace from the field names
        readCSV = csv.DictReader(
            (line.replace("\0", "") for line in reader), delimiter="|"
        )
        readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

        for row in readCSV:
            cRow = {k: v.strip() for k, v in row.items()}
            config = cRow["Config"]
            database[config] = Config(
                domain="N/A",
                status=cRow["Status"],
                lastSeen=datetime.strptime(cRow["LastSeen"], dateFormat),
                expires=datetime.strptime(cRow["Expires"], dateFormat),
            )
    return database


##############################################################################80
# Function to save device database to CSV
##############################################################################80
def saveDatabase(filepath, data):
    cPrint("Saving device database...", "BLUE") if args.debug else None
    header = list(data[next(iter(data))]._fields) if data else []

    with open(filepath, "w") as writer:
        writeCSV = csv.writer(writer)
        header = ["Config", "Status", "LastSeen", "Expires"]
        header = "{:^20}|{:^10}|{:^10}|{:^10}".format(*header).split("|", 0)
        writeCSV.writerow(header)

        for config, tuple in data.items():
            lastSeen = tuple.lastSeen.strftime(dateFormat)
            expires = tuple.expires.strftime(dateFormat)
            details = [config, tuple.status, lastSeen, expires]
            details = "{:<19} |{:^10}|{:^10}|{:^10}".format(*details).split("|", 0)
            writeCSV.writerow(details)
    return True


##############################################################################80
# Pull certificate details from Certbot
##############################################################################80
def checkExpiredCerts(database):
    cPrint(f"Pulling cert details...", "BLUE") if args.debug else None
    # Run "certbot certificates" to get details of all certificates
    certResult = subprocess.run(
        ["certbot", "certificates"], capture_output=True, text=True
    )
    certOutput = certResult.stdout

    # Parse the output to extract certificate details
    certs = []
    for cert in certOutput.split("Certificate Name:")[1:]:
        name = re.search(r"^\s*(\S+)", cert).group(1)
        domains = re.search(r"Domains:\s*(.+)", cert).group(1).strip().split()
        expiry = re.search(r"Expiry Date:.*?(\d{4}-\d{2}-\d{2})", cert).group(1)
        expiry = datetime.strptime(expiry, "%Y-%m-%d")

        for domain in domains:
            for config, tuple in database.items():
                if tuple.domain == domain:
                    tuple = tuple._replace(expires=expiry)
                    database[config] = tuple

    return database


##############################################################################80
# Pull enabled sites from apache2
##############################################################################80
def readEnabledConfigs(database):
    activeConfs = set()

    for conf in os.listdir(enabledConfigs):
        if not conf.endswith(".conf"):
            continue
        domain = ""

        fullPath = os.path.join(enabledConfigs, conf)

        with open(fullPath, "r") as file:
            lines = file.readlines()

        formatted_lines = []
        indentLevel = 0

        for line in lines:
            stripped_line = line.strip()
            if "ServerName" in line or "ServerAlias" in line:
                parts = line.split()
                if len(parts) > 1:
                    test = parts[1].strip().replace(";", "").replace(",", "")
                    if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", test):
                        domain = test

            # Adjust indent level based on the line content
            if re.match(r"</\w+>", stripped_line):  # Closing tag
                indentLevel -= 1

            # Apply indentation
            if stripped_line:  # Apply indentation only if the line is not blank
                formatted_lines.append("    " * indentLevel + stripped_line)
            else:
                formatted_lines.append("")

            if re.match(r"<\w+[^>]*>", stripped_line):  # Opening tag
                indentLevel += 1

        with open(fullPath, "w") as file:
            file.write("\n".join(formatted_lines) + "\n")

        activeConfs.add((conf[:-5], domain))

    for conf, domain in activeConfs:
        tuple = database.get(
            conf, Config(domain=domain, status="new", lastSeen=TN00, expires=False)
        )
        tuple = tuple._replace(lastSeen=TN00)
        tuple = tuple._replace(domain=domain)
        database[conf] = tuple

    return database


##############################################################################80
# Helper function to execute commands
##############################################################################80
def tryCommand(command, text):
    command = ["sudo", "certbot"] + command
    if args.test:
        return print(" ".join(command))
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=600
        )
        return "Successfully" in result.stdout  # Check for success message
    except subprocess.CalledProcessError as e:
        cPrint(f"{text}: {e}", "RED") if args.debug else None
        cPrint(f"Output: {e.output}", "RED") if args.debug else None
        cPrint(f"Error: {e.stderr}", "RED") if args.debug else None
        return False


##############################################################################80
# Function to install new certificates in the configuration files
##############################################################################80
def installCert(domain):
    cPrint(f"Installing cert for {domain}...", "BLUE") if args.debug else None

    command = [
        "--apache",
        "--cert-name",
        domain,
        "--non-interactive",
    ]

    return tryCommand(command, f"Installation error on {domain}")


##############################################################################80
# Attempt to request certs
##############################################################################80
def requestCert(domain):
    cPrint(f"Requesting cert for {domain}...", "BLUE") if args.debug else None
    domains = ["-d", domain]
    if domain.startswith("www."):
        root = domain[4:]  # Strip 'www.'
        domains += ["-d", f"{root}"]

    command = (
        [
            "certonly",
            "--non-interactive",
            "--dns-cloudflare",
            "--dns-cloudflare-credentials",
            "/etc/security/cloudflare.ini",
        ]
        + domains
        + ["--cert-name", domain]
    )

    return tryCommand(command, f"Requesting error on {domain}")


##############################################################################80
# Attempt to renew certs
##############################################################################80
def renewCerts(domain):
    cPrint(f"Renewing cert for {domain}...", "BLUE") if args.debug else None
    domains = ["-d", domain]
    if domain.startswith("www."):
        root = domain[4:]  # Strip 'www.'
        domains += ["-d", f"{root}"]

    command = (
        [
            "certonly",
            "--force-renewal",
            "--dns-cloudflare",
            "--dns-cloudflare-credentials",
            "/etc/security/cloudflare.ini",
        ]
        + domains
        + ["--cert-name", domain]
    )
    return tryCommand(command, f"Renewal error on {domain}")


##############################################################################80
# Attempt to revoke certs
##############################################################################80
def revokeCert(domain):
    cPrint(f"Revoking cert for {domain}...", "BLUE") if args.debug else None
    command = [
        "revoke",
        "--cert-name",
        domain,
        "--delete-after-revoke",
    ]

    return tryCommand(command, f"Revocation error on {domain}")


##############################################################################80
# Begin Main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()
    subject, message = "", []

    database = loadDatabase(datapath)

    try:
        database = readEnabledConfigs(database)
        database = dict(sorted(database.items()))

        database = checkExpiredCerts(database)

        for config, tuple in database.items():
            cPrint(f"Processing {config}...", "BLUE") if args.debug else None
            domain = tuple.domain
            status = tuple.status
            lastSeen = tuple.lastSeen
            expires = tuple.expires

            if status == "new" and requestCert(domain):
                # Ensure installation after requesting new cert
                if installCert(domain):
                    message.append(f"\n\t- Activated {domain}")
                    status = "active"
                    expires = TP90
                else:
                    cPrint(f"Failed install on {domain}", "RED") if args.debug else None

            elif status == "active":
                if lastSeen < TM30 and revokeCert(domain):
                    message.append(f"\n\t- Revoked {domain}")
                    status = "revoked"
                if expires < TP30 and renewCerts(domain):
                    message.append(f"\n\t- Renewed {domain}")
                    expires = TP90

            tuple = tuple._replace(status=status, lastSeen=lastSeen, expires=expires)
            database[config] = tuple

        saveDatabase(datapath, database)

        if len(message) > 0 or args.test:
            cPrint("Certbot renewals, sending notification...", "GREEN")
            subject = f"Certbot updates for {len(message)} domains"
            message = "<b>Domains updated:</b>" + "".join(message)

        else:
            cPrint("No Certbot renewals.", "BLUE")

    except RuntimeError as err:
        cPrint("Certbot error occurred, sending notification...", "RED")
        subject = "Certbot renewal error"
        message = str(err)

    if len(message) > 0 or args.test:
        sendNotification(subject, message)

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)


if __name__ == "__main__":
    main()
