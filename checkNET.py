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
from utils import send, hasFlag, cPrint, SCANID, formatIP

DEBUG = hasFlag("d")
VERBOSE = hasFlag("v")
NOSCAN = hasFlag("n")

# This function will launch NMAP and scan the network mask you provided.
def getNmapScan(SCANID, netRange):
    scanlog = "data/scanlog.xml"
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
            f.write(f"{mac}\t{vendor}\t{ip}\n")

        scan[mac] = {"name": vendor, "vendor": vendor, "ip": ip, "lSeen": SCANID}

    if DEBUG:
        f.close
    return scan

netRange = "192.168.1.1/24"
scan = getNmapScan(SCANID, netRange)  # SCAN NETWORK
try:
   os.makedirs("data/devices", exist_ok=True)
except Exception as e:
        cPrint(f"Error: {e}")


# This function will check the last scan for any devices that are not listed in the whitelist.
def validateScan(SCANID, scan):
    newDevices = {}

    for mac in scan:
        path = f"data/devices/{mac}"
        device = {}

        if os.path.exists(path):
            f = open(path)
            device = json.load(f)
        else:
            device["mac"] = mac
            device["name"] = "unknown"
            device["status"] = "intruder"
            device["fSeen"] = SCANID
            device["ip"] = []

        ip = scan[mac]["ip"]
        if ip not in device["ip"]:
            device["ip"].insert(0,ip)

        device["lSeen"] = scan[mac]["lSeen"]

        if not "vendor" in device:
            device["vendor"] = scan[mac]["vendor"]

        if not device["status"] or device["status"] != "allowed":
            cPrint(f'New device detected: {mac} by {scan[mac]["vendor"]} on {scan[mac]["ip"]}')
            f = open(path, "w")
            f.write(json.dumps(device, indent=4, sort_keys=True))
            f.close()
            newDevices[mac] = device

        #cPrint(f"{mac} called {device['name']}")

    return newDevices

newDevices = validateScan(SCANID, scan)

if len(newDevices) > 0:
    cPrint("New devices found, sending notification...")

    text = "<b>New devices:</b>"

    for k, v in newDevices.items():
        ip, vendor = v["ip"][0], v["vendor"]
        if vendor == "unknown": vendor = f"<font color='#ff4d3e'>{vendor}</font>"
        #vendor = (vendor[:39] + "...") if len(vendor) > 41 else vendor
        text += f"\n\t -{k} by {vendor} on {ip}"

    subject = f"{len(newDevices)} new device(s) detected"

    if DEBUG:
        print(text)
    else:
        send(subject,text)
    exit(0)

else:
    cPrint("No new devices found.")
    exit(0)
