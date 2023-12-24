#!/usr/bin/env python3

# Device intrusion script
# This script will scan the network of your choice and will alert you of devices not present in the whitelist. The whitelist is a list of MAC address that YOU trust. Every time you run the detection script, a list of detected devices will be written in "devices.mac".
# By default, all devices will show as untrusted.

import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import json
import csv
import requests
from collections import namedtuple
from datetime import datetime, timedelta
from utils import send, hasFlag, cPrint, SCANID, formatIP

DEBUG = hasFlag("d")
NOSCAN = hasFlag("n")

scanpath = "data/scanlog.xml"
datapath = "data/devices.csv"
netRange = "192.168.1.1/24"
thirtyDaysAgo = datetime.now() - timedelta(days=30)

##############################################################################80
# Launch NMAP and scan the network mask provided
##############################################################################80
def getNmapScan(netRange, scanlog):

    # Run nmap scan of netRange, save xml to scanlog file
    if not NOSCAN:
        try:
            subprocess.run(["sudo", "nmap", "-v", "-sn", netRange, "-oX", scanlog], check=True, capture_output=True)

        except subprocess.CalledProcessError as e:
            print(f"Error running nmap: {e}")
            exit(127)

    # Open scanlog file and find root
    try:
        root = ET.parse(scanlog).getroot()
    except ET.ParseError as e:
        print(f"Error parsing scanlog: {e}")
        exit(1)

    hosts = root.findall("./host")
    if not hosts:
        return {}

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
                    ip = formatIP(attrib.attrib["addr"])
                if "vendor" in attrib.attrib:
                    vendor = attrib.attrib["vendor"]
                else:
                    vendor = "unknown"
        if state == "down":
            continue

        if mac == "":
            continue

        if DEBUG:
            cPrint(f"{mac}\t{vendor}\t{ip}")

        scan.append({"mac": mac, "vendor": vendor, "ip": ip, "lSeen": SCANID})

    return scan


Device = namedtuple("Device", ("Status Name MAC IP FirstHeard LastHeard Vendor"))
##############################################################################80
# Function to load device databas from CSV
##############################################################################80
def loadDatabase(path):
    database = {}
    if os.path.exists(path):
        with open(path, mode='r') as f:
            # Create a DictReader, and then strip whitespace from the field names
            readCSV = csv.DictReader((line.replace('\0', '') for line in f), delimiter='|')
            readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

            for row in readCSV:
                cleaned_row = {k: v.strip() for k, v in row.items()}
                database[cleaned_row['MAC']] = Device(**cleaned_row)
    return database
    
##############################################################################80
# Function to save device database to CSV
##############################################################################80
def saveDatabase(path, data):
    header = list(data[next(iter(data))]._fields) if data else []

    with open(path, "w") as f:
        writer = csv.writer(f)
        header = "{:^10}|{:^30}|{:^17}|{:^15}|{:^12}|{:^12}|{:^30}".format(*header).split("|", 0)
        writer.writerow(header)

        for mac, details in data.items():
            # Parse the LastHeard date and update the status if it's more than 30 days ago
            lastHeard = datetime.strptime(details.LastHeard, '%Y%m%d%H%M')  # Adjust the format if different

            if lastHeard < thirtyDaysAgo:
                details = details._replace(Status="inactive")

            details = "{:^10}|{:<30}|{:>17}|{:^15}|{:>12}|{:>12}|{:<30}".format(*details).split("|", 0)
            writer.writerow(details)
    return True

##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def searchVendor(mac):
    url = f'https://api.macvendors.com/{mac}'
    try:
        response = requests.get(url)
        if DEBUG:
            cPrint(response.text)
        if response.status_code == 200:
            return response.text  # The vendor name
        else:
            return "unknown"
    except requests.RequestException:
        return "failed"

##############################################################################80
# Parse scan to determine new devices, update devices.csv
##############################################################################80
def processScan(scan, database):
    for device in scan:
        mac = device["mac"]
        ip = device["ip"]
        device = database.get(mac, Device(Status="intruder", Name="unknown", MAC=mac, IP=ip, FirstHeard=SCANID, LastHeard=SCANID, Vendor="unknown"))

        # Check if the scan information exists on a separate json
        path = f"data/devices/{mac}"
        if os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
                oldData = Device(Status=d["status"], Name=d["name"], MAC=d["mac"], IP=ip, FirstHeard=SCANID, LastHeard=SCANID, Vendor=d["vendor"])
                device = oldData

        if device.Status == "inactive":
            device = device._replace(Status="resurfaced")
        elif device.Status == "resurfaced":
            device = device._replace(Status="active")

        vendor = device.Vendor
        if vendor == "unknown":
            vendor = searchVendor(mac)

        # Update data to the latest scan
        device = device._replace(LastHeard=SCANID, IP=ip, Vendor=vendor)

        # Update the database with the new or updated device
        database[mac] = device

    return database

##############################################################################80
# Pretty print device details
##############################################################################80
def processNewDevices(database):
    newDevices = 0
    text = "<b>New devices:</b>"
    for mac, device in database.items():
        if device.Status != "allowed":
            cPrint(f'Device detected: {device.MAC} by {device.Vendor} on {device.IP}')
            newDevices += 1
            ip, vendor = device.IP, device.Vendor
            vendor = f"<font color='#ff4d3e'>{vendor}</font>" if vendor == "unknown" else vendor
            type = "detected" if device.Status == "intruder" else "resurfaced"
            text += f"\n\t - {mac} {type} on {ip} by {vendor}."

    if newDevices:
        cPrint("New devices found, sending notification...")
        subject = f"{newDevices} new device(s) detected"
        send(subject, text) if not DEBUG else print(text)
    else:
        cPrint("No new devices found.")


##############################################################################80
# Being Main execution
##############################################################################80
scan = getNmapScan(netRange, scanpath)
data = loadDatabase(datapath)

data = processScan(scan, data)
processNewDevices(data)
saveDatabase(datapath, data)
