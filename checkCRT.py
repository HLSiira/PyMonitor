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
from datetime import datetime
from utils import checkSudo, cPrint, getBaseParser, sendNotification

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Leverages Certbot to renew SSL Certs. Requires root privileges.")
args = parser.parse_args()

##############################################################################80
# Combine subdomains into a more digestable format
##############################################################################80
def combineSubdomains(domains):
    cPrint(f"Combining subdomains...", "BLUE") if args.debug else None
    domainGroups = {}
    for domain in domains:
        # Extract the main domain and subdomain part
        parts = domain.split(".")
        mainDomain = ".".join(parts[-2:])
        subdomain = ".".join(parts[:-2])

        if mainDomain not in domainGroups:
            domainGroups[mainDomain] = set()

        if subdomain and subdomain != "www":
            domainGroups[mainDomain].add(subdomain)

    combined = []
    for mainDomain, subdomains in domainGroups.items():
        if subdomains:
            subdomainsStr = ", ".join(sorted(subdomains))
            mainDomain = f"{mainDomain} <i>(+{subdomainsStr})</i>"

        combined.append(mainDomain)

    return sorted(combined, key=lambda d: d.split(" ", 1)[0])

##############################################################################80
# Pull certificate details from Certbot
##############################################################################80
def getCertificateDetails():
    cPrint(f"Pulling cert details...", "BLUE") if args.debug else None    
    # Run "certbot certificates" to get details of all certificates
    certResult = subprocess.run(["certbot", "certificates"], capture_output=True, text=True)
    certOutput = certResult.stdout

    # Parse the output to extract certificate details
    certs = []
    for cert in certOutput.split("Certificate Name:")[1:]:
        name = re.search(r"^\s*(\S+)", cert).group(1)
        domains = re.search(r"Domains:\s*(.+)", cert).group(1).strip().split()
        domains = combineSubdomains(domains)
        expiry = re.search(r"Expiry Date:.*?(\d{4}-\d{2}-\d{2})", cert).group(1)
        expiry = datetime.strptime(expiry, "%Y-%m-%d").strftime("%Y%m%d")  # Convert string to datetime
        certs.append({"name": name, "domains": domains, "expiry": expiry})
    
    return certs[0]

##############################################################################80
# Attempt to renew certs
##############################################################################80
def renewCerts():
    cPrint(f"Renewing certs...", "BLUE") if args.debug else None
    try:
        result = subprocess.run(["certbot", "renew"], capture_output=True, text=True, timeout=600)
        return "Congratulations" in result.stdout
    except Exception as e:
        raise RuntimeError(f"Certbot renewal error: {e}")

##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()
    subject, message = "", ""
    certRenewed = False

    try:
        certRenewed = renewCerts()

        if certRenewed or args.test:
            cPrint("Certbot renewals, sending notification...", "GREEN")
            cert = getCertificateDetails()
            subject = f"Certbot renewal for {len(cert['domains'])} domains"
            message = "<b>Domains renewed:</b>"
            for domain in cert["domains"]:
                message += f"\n\t- {domain}"
            message += f"\n<b>Cert expires: {cert['expiry']}</b>"

        else:
            cPrint("No Certbot renewals.", "BLUE")

    except RuntimeError as err:
        cPrint("Certbot error occurred, sending notification...", "RED")
        subject = "Certbot renewal error"
        message = str(err)

    if certRenewed or args.test:
        sendNotification(subject, message)

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)   

if __name__ == "__main__":
    main()