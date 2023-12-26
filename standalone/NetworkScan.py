#!/usr/bin/env python3

##############################################################################80
# NetworkScan 20231224 - Device intrusion script
##############################################################################80
# This script will scan the network of your choice and will alert you of devices
# not listed as "allowed" in the database. The alerts are sent through PushOver.
# By default, all devices will show as untrusted.
# USAGE via CRON: (Runs every 10 minutes, must be ROOT user)
#   */10 * * * * cd /path/to/folder && ./checkNET.py 2>&1
# USAGE via CLI:
#   cd /path/to/folder && ./checkNET.py (-dn)
#   Flags:  -d: prints debug messages and doesn't send notification
#           -n: to use a cached nmap scan, created on first run
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/docs/LICENSE.md for more.
# This information must remain intact.
##############################################################################80

import os, sys, socket
import subprocess
import xml.etree.ElementTree as ET
import csv
import requests
from collections import namedtuple
from datetime import datetime, timedelta

##############################################################################80
# Configuration settings
##############################################################################80
user_key = "PROVIDEYOUROWNTOKENHERE"
api_token = "PROVIDEYOUROWNTOKENHERE"

scanpath = "data/scanlog.xml"
datapath = "data/devices.csv"
netRange = "192.168.1.1/24"
deleteAfter = 90 #days

##############################################################################80
# Global variables
##############################################################################80
DEBUG = len(sys.argv) > 1 and "d" in sys.argv[1] # Flag to print debug statements
NOSCAN = len(sys.argv) > 1 and "n" in sys.argv[1] # Flag to skip nmap scan and use the cache
SCANID = datetime.now().strftime("%Y%m%d%H%M") # SCANID is the date/time
NAME = os.path.basename(sys.argv[0])
Device = namedtuple("Device", ("Status Name MAC IP FirstHeard LastHeard Vendor"))

##############################################################################80
# Print helper to add color: Red(0), Blue(1), Green(2), and Reset(3)
##############################################################################80
CLRS = ["\033[31m", "\033[32m", "\033[34m", "\033[0m"]
def cPrint(msg, clr = 3):
    clr = CLRS[clr]
    print(clr + f"{msg}" + CLRS[3])

##############################################################################80
# Using Pushover credentials, send a notification
##############################################################################80
def sendNotification(subject, message):
    host = socket.gethostname().title()
    data = {
        'token': api_token,
        'user': user_key,
        'message': message,
        'title': f"{host}: {subject}",
        'html' : 1,
        'priority': 0,
        'ttl': 43200
    }

    response = requests.post('https://api.pushover.net/1/messages.json', data=data)
    # Print the API's response which can be useful for debugging or confirmation    
    cPrint(response.text, 2) if DEBUG else None
    

##############################################################################80
# Launch NMAP and scan the network mask provided
##############################################################################80
def getNmapScan(netRange, scanlog):

    # Run nmap scan of netRange, save xml to scanlog file
    if not NOSCAN:
        try:
            subprocess.run(["sudo", "nmap", "-v", "-sn", netRange, "-oX", scanlog], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            cPrint(f"\tError running nmap: {e}", 1)
            exit(127)

    # Open scanlog file and find root
    try:
        root = ET.parse(scanlog).getroot()
    except ET.ParseError as e:
        cPrint(f"\tError parsing scanlog: {e}", 1)
        exit(1)

    hosts = root.findall("./host")
    if not hosts:
        cPrint(f"\tError finding hosts in scanlog", 1)
        exit(1)

    scan = []
    for child in hosts:
        state = mac = ip = vendor = ""
        for attrib in child:
            if attrib.tag == "status":
                state = attrib.attrib["state"]
            if attrib.tag == "address":
                if attrib.attrib["addrtype"] == "mac":
                     mac = attrib.attrib["addr"]
                if attrib.attrib["addrtype"] == "ipv4":
                    # Format the IPs with padded zeros to allow for visual alignment
                    octets = attrib.attrib["addr"].split('.')
                    octets = [octet.zfill(3) for octet in octets]
                    ip = ".".join(octets)
                if "vendor" in attrib.attrib:
                    vendor = attrib.attrib["vendor"]
                else:
                    vendor = "unknown"

        if state == "down" or mac == "":
            continue

        cPrint(f"\tFound: {mac}\t{vendor}\t{ip}", 2) if DEBUG else None

        scan.append({"mac": mac, "vendor": vendor, "ip": ip})

    return scan

##############################################################################80
# Load device database from CSV
##############################################################################80
def loadDatabase(path):
    cPrint(f"\tLoading database...", 2) if DEBUG else None
    database = {}
    if os.path.exists(path):
        with open(path, mode="r") as f:
            # Create a DictReader, and then strip whitespace from the field names
            readCSV = csv.DictReader((line.replace("\0", "") for line in f), delimiter="|")
            readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

            for row in readCSV:
                cleaned_row = {k: v.strip() for k, v in row.items()}
                database[cleaned_row["MAC"]] = Device(**cleaned_row)
    return database
    
##############################################################################80
# Save device database to CSV
##############################################################################80
def saveDatabase(path, data):
    cPrint(f"\tSaving database...", 2) if DEBUG else None
    header = list(data[next(iter(data))]._fields) if data else []
    expiration = datetime.now() - timedelta(days=deleteAfter) if deleteAfter else "N/A"

    with open(path, "w") as f:
        writer = csv.writer(f)
        header = "{:^10}|{:^30}|{:^17}|{:^15}|{:^12}|{:^12}|{:^30}".format(*header).split("|", 0)
        writer.writerow(header)

        for mac, device in data.items():
            # Parse the LastHeard date and update the status if it"s more than 30 days ago
            lastHeard = datetime.strptime(device.LastHeard, "%Y%m%d%H%M")  # Adjust the format if different

            # Only write rows where the date is within the expiration
            if expiration == "N/A" or lastHeard > expiration:
                device = "{:^10}|{:<30}|{:>17}|{:^15}|{:>12}|{:>12}|{:<30}".format(*device).split("|", 0)
                writer.writerow(device)
            elif DEBUG:
                cPrint(f"\tDeleting inactive device: {device.MAC} by {device.Vendor}", 1)
    return True

##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def searchVendor(mac):
    cPrint(f"\tSearching {mac}...", 2) if DEBUG else None
    url = f"https://api.macvendors.com/{mac}"
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            cPrint(f"\t{response.text}",1) if DEBUG else None
            return response.text  # The vendor name
        else:
            cPrint(f"\t{response.text}",0) if DEBUG else None
            return "unknown"
    except requests.RequestException:
        return "failed"

##############################################################################80
# Parse scan to determine new devices, update database
##############################################################################80
def processScan(scan, database):
    cPrint(f"\tComparing scan against database...", 2) if DEBUG else None
    for device in scan:
        mac = device["mac"]
        ip = device["ip"]
        device = database.get(mac, Device(Status="intruder", Name="unknown", MAC=mac, IP=ip, FirstHeard=SCANID, LastHeard=SCANID, Vendor="unknown"))

        vendor = device.Vendor
        if vendor == "unknown":
            vendor = searchVendor(mac)

        # Update data to the latest scan
        device = device._replace(LastHeard=SCANID, IP=ip, Vendor=vendor)

        # Update the database with the new or updated device
        database[mac] = device

    return database

##############################################################################80
# Process databse for new devices and send notification if needed
##############################################################################80
def processNewDevices(database):
    cPrint(f"\tProcessing new devices...", 2) if DEBUG else None
    newDevices = 0
    text = "<b>New devices:</b>"
    for mac, device in database.items():
        if device.Status != "allowed":
            cPrint(f"\tDevice detected: {device.MAC} by {device.Vendor} on {device.IP}", 0)
            newDevices += 1
            ip, vendor = device.IP, device.Vendor
            vendor = f"<font color='#ff4d3e'>{vendor}</font>" if vendor == "unknown" else vendor
            type = "detected" if device.Status == "intruder" else "resurfaced"
            text += f"\n\t - {mac} {type} on {ip} by {vendor}."

    if newDevices:
        cPrint(f"\tNew devices found, sending notification...", 2)
        subject = f"{newDevices} new device(s) detected"
        sendNotification(subject, text) if not DEBUG else print(f"\t{text}")
    else:
        cPrint(f"\tNo new devices found.", 1)

##############################################################################80
# Being Main execution
##############################################################################80
cPrint(f"Beginning Network Scan {SCANID}...")
scan = getNmapScan(netRange, scanpath)
data = loadDatabase(datapath)

data = processScan(scan, data)
processNewDevices(data)
saveDatabase(datapath, data)
cPrint(f"Network Scan {SCANID} completed.")