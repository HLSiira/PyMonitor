#!/usr/bin/env python3

import subprocess
import os, sys
import re
from datetime import datetime

from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")

def combine_subdomains(domains):
    domain_groups = {}
    for domain in domains:
        # Extract the main domain and subdomain part
        parts = domain.split('.')
        main_domain = '.'.join(parts[-2:])
        subdomain = '.'.join(parts[:-2])

        if main_domain not in domain_groups:
            domain_groups[main_domain] = set()

        if subdomain and subdomain != "www":
            domain_groups[main_domain].add(subdomain)

    combined = []
    for main_domain, subdomains in domain_groups.items():
        # if "www" in subdomains:
        #     subdomains.remove("www")
        #     main_domain = "<i>www.</i>" + main_domain
        # else:
        #     main_domain = "    " + main_domain
            
        if subdomains:
            # Combine subdomains into a single entry
            subdomains_str = ', '.join(sorted(subdomains))
            main_domain = f"{main_domain} <i>(+{subdomains_str})</i>"

        combined.append(main_domain)

    return sorted(combined, key=lambda d: d.split(' ', 1)[0])

def get_certificate_details():
    # Run 'certbot certificates' to get details of all certificates
    cert_result = subprocess.run(['certbot', 'certificates'], capture_output=True, text=True)
    cert_output = cert_result.stdout

    # Parse the output to extract certificate details
    certs = []
    for cert in cert_output.split("Certificate Name:")[1:]:
        name = re.search(r'^\s*(\S+)', cert).group(1)
        domains = re.search(r'Domains:\s*(.+)', cert).group(1).strip().split()
        domains = combine_subdomains(domains)
        expiry = re.search(r'Expiry Date:.*?(\d{4}-\d{2}-\d{2})', cert).group(1)
        expiry = datetime.strptime(expiry, "%Y-%m-%d").strftime("%Y%m%d")  # Convert string to datetime
        certs.append({'name': name, 'domains': domains, 'expiry': expiry})
    
    return certs[0]

subject, message = "",""

try:
    # Run the certbot renew command
    result = subprocess.run(["certbot", "renew"], capture_output=True, text=True, timeout=600)
    output = result.stdout
    
#     output = """
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Processing /etc/letsencrypt/renewal/20231223.conf
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Simulating renewal of an existing certificate for promo.airpoweraugusta.com and 30 more domains

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Processing /etc/letsencrypt/renewal/promo.airpoweraugusta.com.conf
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Simulating renewal of an existing certificate for promo.airpoweraugusta.com and 30 more domains

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Congratulations, all simulated renewals succeeded:
#   /etc/letsencrypt/live/20231223/fullchain.pem (success)
#   /etc/letsencrypt/live/promo.airpoweraugusta.com/fullchain.pem (success)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -"""

    # Check if any certificates were actually renewed
    if "Congratulations" in output:
        # Get updated certificate details
        cert = get_certificate_details()
        
        # Extracting domain names and their new expiry dates
        domains = cert['domains']
        # expiries = re.findall(r"(?:VALID: )[^\(]+(\([^)]+\))", output)

        subject = f"Certbot renewal for {len(domains)} domains"
        message = "<b>Domains renewed:</b>"

        for domain in domains:
            message += f"\n\t- {domain}"
            # message += f"Name: {cert['name']}, Domains: {', '.join(cert['domains'])}, Expiry: {cert['expiry']}\n"
        
        message += f"\n<b>Cert expires: {cert['expiry']}</b>"


        cPrint("Certbot renewals, sending notification...")
    else:
        cPrint("No Certbot renewals.")

except Exception as e:
    cPrint("Certbot error occurred, sending notification...")
    subject = "Cerbot error"
    message = f"Certificate renewal error:\n{e}"

if DEBUG:
    print(subject)
    print(message)
else:
    send(subject, message)

exit(0)
