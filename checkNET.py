#!/usr/bin/python3

# Device intrusion script

# This script will scan the network of your choice and will alert you of devices not present in the whitelist. The whitelist is a list of MAC address that YOU trust. Every time you run the detection script, a list of detected devices will be written in "devices.mac".
# By default, all devices will show as untrusted.

# Edit devices.mac if needed and run the script below. It will mark as trusted every devices in the list.

# sudo ./trust-devices.py  data.db devices.mac

# Author: Luc Raymond lucraymond@gmail.com
# License: MIT
# Requirements : nmap and python
# Privileges: sudo (for nmap to get the mac address)

import os, sys
import subprocess
import xml.etree.ElementTree as ET

import json
from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")
VERBOSE = hasFlag("v")
NOSCAN = hasFlag("n")

# This function will launch NMAP and scan the network mask you provided.
def getNmapScan(SCANID, netRange):
    scanlog = "samples/scanlog.xml"
    if DEBUG:
        f = open("samples/devices.mac", "w")

    # for debugging, if the scanlog already exists, don"t scan again
    if not (NOSCAN and os.path.exists(scanlog)):
        output = subprocess.run(
            ["sudo", "nmap", "-v", "-sn", netRange, "-oX", scanlog], capture_output=True
        )
        if output.returncode != 0:
            exit(127)

    root = (ET.parse(scanlog)).getroot()
    hosts = root.findall("./host")
    if not hosts:
        return

    scan = {}
    for child in hosts:
        state = mac = ip = vendor = ""
        for attrib in child:
            if attrib.tag == "status":
                state = attrib.attrib["state"]
            if attrib.tag == "address":
                if attrib.attrib["addrtype"] == "mac":
                    mac = attrib.attrib["addr"]
                if attrib.attrib["addrtype"] == "ipv4":
                    ip = attrib.attrib["addr"]
                if "vendor" in attrib.attrib:
                    vendor = attrib.attrib["vendor"]
        if state == "down":
            continue

        if mac == "":
            continue

        if DEBUG:
            f.write(f"{mac}\t{vendor}\t{ip}\n")

        scan[mac] = {"name": vendor, "vendor": vendor, "ip": ip, "lSeen": SCANID}

    if DEBUG:
        f.close
    return scan


# This function will check the last scan for any devices that are not listed in the whitelist.
def validateScan(SCANID, devices, scan):
    iCount = {}

    for mac in scan:
        if mac not in devices or devices[mac]["status"] != "allowed":
            device = scan[mac]
            device["name"] = "unknown"
            device["status"] = "intruder"
            device["fSeen"] = SCANID
            devices[mac] = device

            alert = f'Intruder detected: IP:{devices[mac]["ip"]}, VENDOR:{devices[mac]["vendor"]}'
            iCount[mac] = device
            if not DEBUG:
                cPrint(alert)
        else:
            devices[mac]["ip"] = scan[mac]["ip"]
            devices[mac]["lSeen"] = scan[mac]["lSeen"]
            devices[mac]["vendor"] = scan[mac]["vendor"]

    # now write output to a file
    f = open(database, "w")
    # magic happens here to make it pretty-printed
    f.write(json.dumps(devices, indent=4, sort_keys=True))
    f.close()
    return iCount


# Opening JSON file
database = "data/devices.json"
devices = {}
if os.path.exists(database):
    f = open(database)
    devices = json.load(f)

netRange = "192.168.1.1/24"
scan = getNmapScan(SCANID, netRange)  # SCAN NETWORK
iCount = validateScan(SCANID, devices, scan)

if len(iCount) > 0:
    cPrint("New devices found, sending notification...")

    text = "<b>New devices:</b>"
    
    for k, v in iCount.items():
        ip, vendor = v["ip"], v["vendor"]
        vendor = (vendor[:39] + "...") if len(vendor) > 41 else vendor
        text += f"\n\t -{ip}\t {vendor}/{k}"
    
    subject = f"{len(iCount)}New device(s) detected"
    
    if DEBUG:
        print(text)
    else:
        send(subject,text)
    exit(0)

elif not DEBUG:
    cPrint("No new devices found.")
    exit(0)
