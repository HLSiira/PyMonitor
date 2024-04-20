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
from utils import checkSudo, cPrint, getBaseParser, sendNotification, SCANID

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Leverages Certbot to request, renew, or revoke SSL Certs. Requires root privileges.")
args = parser.parse_args()
datapath = "data/domains.csv"
TM30 = datetime.now() - timedelta(days=30) # 30 days ago
TP30 = datetime.now() + timedelta(days=30) # 30 days from now
TP90 = datetime.now() + timedelta(days=90) # 90 days from now

Domain = namedtuple("Domain", ("status lastActive expires"))
##############################################################################80
# Pull enabled sites from apache2
##############################################################################80
def getActiveDomains(database):
    activeDomains = set()
    config_path = "/etc/apache2/sites-enabled"
    for filename in os.listdir(config_path):
        with open(os.path.join(config_path, filename), 'r') as file:
            for line in file:
                if 'ServerName' in line or 'ServerAlias' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        domain = parts[1].strip().replace(';', '').replace(',', '')
                        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
                                activeDomains.add(domain)

    domainsToRemove = set()
    for domain in activeDomains:
        www_version = 'www.' + domain
        root_version = domain[4:] if domain.startswith('www.') else domain

        if www_version in activeDomains:
            domainsToRemove.add(domain)
    activeDomains.difference_update(domainsToRemove)

    for domain in activeDomains:
        tuple = database.get(domain, Domain(status="new", lastActive=SCANID, expires=False))
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
        return False

    with open(filepath, mode="r") as reader:
        # Create a DictReader, and then strip whitespace from the field names
        readCSV = csv.DictReader((line.replace("\0", "") for line in reader), delimiter="|")
        readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

        for row in readCSV:
            cRow = {k: v.strip() for k, v in row.items()}
            domain = cRow["Domain"]
            database[domain] = Domain(status=cRow["Status"], lastActive=cRow["LastActive"], expires=cRow["Expires"])
    return database

##############################################################################80
# Function to save device database to CSV
##############################################################################80
def saveDatabase(filepath, data):
    cPrint("Saving device database...", "BLUE") if args.debug else None
    header = list(data[next(iter(data))]._fields) if data else []

    with open(filepath, "w") as writer:
        writeCSV = csv.writer(writer)
        header = ['Domain', 'Status', 'LastActive', 'Expires']
        header = "{:^30}|{:^10}|{:^12}|{:^12}".format(*header).split("|", 0)
        writeCSV.writerow(header)

        for domain, tuple in data.items():
            details = [domain, tuple.status, tuple.lastActive, tuple.expires]
            details = "{:>30}|{:^10}|{:>12}|{:>12}".format(*details).split("|", 0)
            writeCSV.writerow(details)
    return True

##############################################################################80
# Attempt to request certs
##############################################################################80
def requestCert(domain):
    cPrint(f"Requesting cert for {domain}...", "BLUE") if args.debug else None
    domains = ['-d', domain]
    if domain.startswith('www.'):
        root = domain[4:]  # Strip 'www.'
        domains += ['-d', f'{root}']

    command = [
        'sudo', 'certbot', 'certonly', '--dns-cloudflare',
        '--dns-cloudflare-credentials', '/etc/security/cloudflare.ini',
        ] + domains + ['--cert-name', domain]

    if args.test:
        return print(' '.join(command))

    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
    except subprocess.CalledProcessError as e:
        cPrint(f"Error requesting cert for {domain}: {e}", "RED") if args.debug else None
        return False

    
##############################################################################80
# Attempt to renew certs
##############################################################################80
def renewCerts(domain):
    cPrint(f"Renewing cert for {domain}...", "BLUE") if args.debug else None
    domains = ['-d', domain]
    if domain.startswith('www.'):
        root = domain[4:]  # Strip 'www.'
        domains += ['-d', f'{root}']

    command = [
        'sudo', 'certbot', 'certonly', '--force-renewal', '--dns-cloudflare',
        '--dns-cloudflare-credentials', '/etc/security/cloudflare.ini'
        ] + domains + ['--cert-name', domain]
        
    if args.test:
        return print(' '.join(command))
        
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
        return "Congratulations" in result.stdout or "Successfully" in result.stdout
    except subprocess.CalledProcessError as e:
        cPrint(f"Certbot renewal error for {domain}: {e}", "RED") if args.debug else None
        return False 

##############################################################################80
# Attempt to revoke certs
##############################################################################80
def revokeCert(domain):
    cPrint(f"Revoking cert for {domain}...", "BLUE") if args.debug else None
    command = [
        'sudo', 'certbot', 'revoke',
        '--cert-name', domain,
        '--delete-after-revoke'
    ]
    
    if args.test:
        return print(' '.join(command))
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
    except subprocess.CalledProcessError as e:
        cPrint(f"Error requesting cert for {domain}: {e}", "RED") if args.debug else None
        return False

##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None
    checkSudo()
    subject, message = "", []
    
    max = 4

    database = loadDatabase(datapath)

    try:
        database = getActiveDomains(database)
        database = dict(sorted(database.items()))

        for domain, tuple in database.items():
            if tuple.status in ["new", "pending"]:
                if max > 0 and requestCert(domain):
                    message.append(f"\n\t- Requested {domain}")
                    tuple = tuple._replace(expires=TP90.strftime("%Y%m%d%H%M"), status="active")
                    max -= 1
                else:
                    message.append(f"\n\t- Pending {domain}")
                    tuple = tuple._replace(expires=TP90.strftime("%Y%m%d%H%M"), status="pending")
            elif tuple.status == "inactive":
                if revokeCert(domain):
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
            message = "<b>Domains updated:</b>" + ''.join(message)

        else:
            cPrint("No Certbot renewals.", "BLUE")

    except RuntimeError as err:
        cPrint("Certbot error occurred, sending notification...", "RED")
        subject = "Certbot renewal error"
        message = str(err)

    if len(message) > 0 or args.test:
        sendNotification(subject, message)

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)   

if __name__ == "__main__":
    main()