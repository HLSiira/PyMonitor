#!/usr/bin/env python3

##############################################################################80
# Creates backups and sends to cloud storage using rClone 20231227
##############################################################################80
# Description: Checks system information and sends notification if outside
# predefined bounderies.
# USAGE via CRON: (Runs every 15 minutes)
#   */15 * * * * cd /path/to/folder && ./checkSYS.py 2>&1 | ./tailog.py
# USAGE via CLI:
#   cd /path/to/folder && ./checkSYS.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/docs/LICENSE.md for more.
##############################################################################80

import os, sys
import subprocess
from datetime import datetime
from utils import cPrint, getBaseParser, sendNotification, CONF, HOSTNAME

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Creates backups and sends to cloud storage using rClone.")
parser.add_argument("-s", "--skipCompress", action="store_true", help="Skip compressing, only backup and cleanup")
args = parser.parse_args()

##############################################################################80
# Configuration Settings
##############################################################################80
BACKUPPATH = CONF["backup"]["backupPath"]

##############################################################################80
# Create backup directory
##############################################################################80
def createDirectory(name):
    cPrint(f"Creating directory for {name}...", "BLUE") if args.debug else None
    backup = f"{BACKUPPATH}/{name}"
    try:
        os.makedirs(backup, exist_ok=True)
        return True, f"Directory creation successful for {name}"
    except subprocess.CalledProcessError:
        return False, f"Directory creation failed on {name}"

##############################################################################80
# 
##############################################################################80
def compress(archive, source):
    cPrint(f"Compressing and saving as {archive}...", "BLUE") if args.debug else None

    try:
        subprocess.run(["tar", "--exclude-vcs", "-zcf", f"{BACKUPPATH}/{archive}", "-C", source, "."], check=True)
        return True, f"{archive} created and stored"
    except subprocess.CalledProcessError:
        return False, f"TAR command failed on {name}"

##############################################################################80
# Delete files older than the expiry period
##############################################################################80
def cleanUp(name, deleteAfter):
    cPrint(f"Deleting archives older than {deleteAfter} days...", "BLUE") if args.debug else None
    backup = f"{BACKUPPATH}/{name}"
    try:
        subprocess.run(["find", f"{backup}", "-type", "f", "-mtime", f"+{deleteAfter}", "-delete"], check=True)
        return True, f"Cleanup successful for {name}"
    except subprocess.CalledProcessError:
        return False, f"Cleanup failed on {name}"

##############################################################################80
# rClone to cloud storage
##############################################################################80
def rCloneToCloud(method="copy"):
    cPrint(f"rCloning to cloud storage...", "BLUE") if args.debug else None
    cloudPath = CONF["backup"]["cloudPath"] + HOSTNAME
    try:
        subprocess.run(["rclone", "sync", BACKUPPATH, cloudPath], check=True, capture_output=True)
        return True, "RClone sync successful"
    except subprocess.CalledProcessError:
        return False, "RClone sync failed"

##############################################################################80
# Begin main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None

    deleteAfter = CONF["backup"]["deleteAfter"]

    metrics = []
    for item in CONF["backup"]["items"]:
        name = item["name"]
        path = item["path"]
        
        metrics.append(createDirectory(name))
        
        if item["compress"] and not args.skipCompress:
            weeknum = datetime.now().strftime("%V")
            archive = f"{name}/{name}-WK{weeknum}.tar.gz"
            metrics.append(compress(archive, path))
            
        if item["cleanup"]:
            metrics.append(cleanUp(name, deleteAfter))
            
    metrics.append(rCloneToCloud())

    message = "<b>Process status:</b>"
    sendNotice = False

    for warning,state in metrics:
        if warning:
            sendNotice = True
        message += f"\n\t- {state}"
        
    if sendNotice or args.test:
        cPrint(f"Error in backup process, sending notification...", "RED")
        subject = "Error in backup process"

        sendNotification(subject, message)            
    else:
        cPrint("Backup successful.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)   

if __name__ == "__main__":
    main()
