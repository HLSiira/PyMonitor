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
from utils import checkSudo, cPrint, getBaseParser, pingHealth, sendNotification, SCANID

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser(
    "Leverages Certbot to request, renew, or revoke SSL Certs. Requires root privileges."
)
args = parser.parse_args()
datapath = "data/domains.csv"
configs = "/etc/apache2/sites-available/"
TM30 = datetime.now() - timedelta(days=30)  # 30 days ago
TP30 = datetime.now() + timedelta(days=30)  # 30 days from now
TP90 = datetime.now() + timedelta(days=90)  # 90 days from now

Domain = namedtuple("Domain", ("status lastActive expires"))

##############################################################################80
# Pull certificate details from Certbot
##############################################################################80
def getCertificateDetails():
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
        expiry = datetime.strptime(expiry, "%Y-%m-%d").strftime(
            "%Y%m%d"
        )  # Convert string to datetime
        certs.append({"name": name, "domains": domains, "expiry": expiry})

    return certs


##############################################################################80
# Pull enabled sites from apache2
##############################################################################80
def getActiveDomains(database):
    activeDomains = set()
    config_path = "/etc/apache2/sites-enabled"
    for filename in os.listdir(config_path):
        with open(os.path.join(config_path, filename), "r") as file:
            for line in file:
                if "ServerName" in line or "ServerAlias" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        domain = parts[1].strip().replace(";", "").replace(",", "")
                        if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
                            activeDomains.add(domain)

    domainsToRemove = set()
    for domain in activeDomains:
        www_version = "www." + domain
        root_version = domain[4:] if domain.startswith("www.") else domain

        if www_version in activeDomains:
            domainsToRemove.add(domain)
    activeDomains.difference_update(domainsToRemove)

    for domain in activeDomains:
        tuple = database.get(
            domain, Domain(status="new", lastActive=SCANID, expires=False)
        )
        tuple = tuple._replace(lastActive=SCANID)
        database[domain] = tuple
    return database


##############################################################################80
# Function to load device databas from CSV
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
            domain = cRow["Domain"]
            database[domain] = Domain(
                status=cRow["Status"],
                lastActive=cRow["LastActive"],
                expires=cRow["Expires"],
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
        header = ["Domain", "Status", "LastActive", "Expires"]
        header = "{:^20}|{:^10}|{:^12}|{:^12}".format(*header).split("|", 0)
        writeCSV.writerow(header)

        for domain, tuple in data.items():
            details = [domain, tuple.status, tuple.lastActive, tuple.expires]
            details = "{:>19} |{:^10}|{:>12}|{:>12}".format(*details).split("|", 0)
            writeCSV.writerow(details)
    return True


##############################################################################80
# Function to remove old certificates on file inside the configuration files
##############################################################################80
def cleanUpConfigs(database):
    cPrint("Cleaning up config files...", "BLUE") if args.debug else None
    for domain in database:
        config = f"{configs}{domain}.conf"
        if not os.path.exists(config):
            domain = domain.lstrip("www.")  # Remove 'www.' from the domain
            config = f"{configs}{domain}.conf"
            if not os.path.exists(config):
                cPrint(
                    f"Config file {domain} does not exist.", "RED"
                ) if args.debug else None
                return

        with open(config, "r") as file:
            lines = file.readlines()

        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped_line = line.strip()

            # Adjust indent level based on the line content
            if re.match(r"</\w+>", stripped_line):  # Closing tag
                indent_level -= 1

            # Apply indentation
            if stripped_line:  # Apply indentation only if the line is not blank
                formatted_lines.append("    " * indent_level + stripped_line)
            else:
                formatted_lines.append("")

            if re.match(r"<\w+[^>]*>", stripped_line):  # Opening tag
                indent_level += 1

        with open(config, "w") as file:
            file.write("\n".join(formatted_lines) + "\n")

        cPrint(f"Cleaned {config} config.", "BLUE") if args.debug else None


##############################################################################80
# Function to install new certiicates in the configuration files
##############################################################################80
def installCert(domain):
    cPrint(f"Installing cert for {domain}...", "BLUE") if args.debug else None

    command = [
        "sudo",
        "certbot",
        "--apache",
        "--cert-name",
        domain,
        "--non-interactive",
    ]

    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=600
        )
        return "Successfully" in result.stdout  # Check for success message
    except subprocess.CalledProcessError as e:
        cPrint(
            f"Certbot installation error for {domain}: {e}", "RED"
        ) if args.debug else None
        cPrint(f"Output: {e.output}", "RED") if args.debug else None
        cPrint(f"Error: {e.stderr}", "RED") if args.debug else None
        return False


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
            "sudo",
            "certbot",
            "certonly",
            "--non-interactive",
            "--dns-cloudflare",
            "--dns-cloudflare-credentials",
            "/etc/security/cloudflare.ini",
        ]
        + domains
        + ["--cert-name", domain]
    )

    if True and args.test:
        print(" ".join(command))
        return True

    try:
        return subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=6000
        )
    except subprocess.CalledProcessError as e:
        (
            cPrint(f"Error requesting cert for {domain}: {e}", "RED")
            if args.debug
            else None
        )
        return False


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
            "sudo",
            "certbot",
            "certonly",
            "--force-renewal",
            "--dns-cloudflare",
            "--dns-cloudflare-credentials",
            "/etc/security/cloudflare.ini",
        ]
        + domains
        + ["--cert-name", domain]
    )

    if args.test:
        return print(" ".join(command))

    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=6000
        )
        return "Congratulations" in result.stdout or "Successfully" in result.stdout
    except subprocess.CalledProcessError as e:
        (
            cPrint(f"Certbot renewal error for {domain}: {e}", "RED")
            if args.debug
            else None
        )
        return False


##############################################################################80
# Attempt to revoke certs
##############################################################################80
def revokeCert(domain):
    cPrint(f"Revoking cert for {domain}...", "BLUE") if args.debug else None
    command = [
        "sudo",
        "certbot",
        "revoke",
        "--cert-name",
        domain,
        "--delete-after-revoke",
    ]

    if args.test:
        return print(" ".join(command))
    try:
        return subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=600
        )
    except subprocess.CalledProcessError as e:
        (
            cPrint(f"Error requesting cert for {domain}: {e}", "RED")
            if args.debug
            else None
        )
        return False


##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()
    subject, message = "", []

    database = loadDatabase(datapath)

    if args.debug:
        activeCerts = getCertificateDetails()
        details = ""

        for cert in activeCerts:
            details += f"\n- {cert['name']} - E{cert['expiry']}: {cert['domains']}"

        print(details)

    try:
        database = getActiveDomains(database)
        database = dict(sorted(database.items()))

        # Clean up all old references before processing any certs
        cleanUpConfigs(database)

        for domain, tuple in database.items():
            cPrint(f"Processing {domain}...", "BLUE") if args.debug else None
            if tuple.status == "new" and requestCert(domain):
                if installCert(domain):  # Ensure installation after requesting new cert
                    message.append(f"\n\t- Activated {domain}")
                    tuple = tuple._replace(
                        expires=TP90.strftime("%Y%m%d%H%M"), status="active"
                    )
                else:
                    cPrint(
                        f"Failed to install cert for {domain}", "RED"
                    ) if args.debug else None
            elif tuple.status == "inactive" and revokeCert(domain):
                message.append(f"\n\t- Revoked {domain}")
                tuple = tuple._replace(status="revoked")
            elif tuple.status == "active":
                lastActive = datetime.strptime(tuple.lastActive, "%Y%m%d%H%M")
                if lastActive < TM30:
                    message.append(f"\n\t- Deactivated {domain}")
                    tuple = tuple._replace(status="inactive")
                expires = datetime.strptime(tuple.expires, "%Y%m%d%H%M")
                if expires < TP30:
                    message.append(f"\n\t- Renewed {domain}")
                    tuple = tuple._replace(expires=TP90.strftime("%Y%m%d%H%M"))
            database[domain] = tuple

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
