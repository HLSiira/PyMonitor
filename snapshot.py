#!/usr/bin/env python3

##############################################################################80
# Automatic rClone Backups 20231227
##############################################################################80
# Description: Creates backups and sends to cloud storage using rClone
# predefined bounderies.
# USAGE via CRON: (Runs every 15 minutes)
#   */15 * * * * cd /path/to/folder && ./checkSYS.py 2>&1 | ./tailog.py
# USAGE via CLI:
#   cd /path/to/folder && ./checkSYS.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -s: Skip compressing, only backup and cleanup.
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
parser.add_argument("-s", "--skipCompress", action="store_true", help="Skip compressing, only backup and cleanup.")
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
        return False, f"Directory creation successful for {name}"
    except subprocess.CalledProcessError:
        return True, f"Directory creation failed on {name}"

##############################################################################80
# 
##############################################################################80
def compress(name, source, compression="xz"):
    cPrint(f"Compressing {name}...", "BLUE") if args.debug else None

    weeknum = datetime.now().strftime("%V")
    try:
        archive = f"{name}/{name}-WK{weeknum}"
        if compression == "gzip": # Fastest, low compression
            archive += ".tar.gz"
            subprocess.run(["tar", "--exclude-vcs", "-zcf", f"{BACKUPPATH}/{archive}", "-C", source, "."], check=True)
            
        elif compression == "zstd": # Fast, medium compression
            archive += ".tar.zst"
            subprocess.run(["tar", "--exclude-vcs", "--zstd", "-cf", f"{BACKUPPATH}/{archive}", "-C", source, "."], check=True)

        elif compression == "xz": # Slowest, highest compression
            archive += ".tar.xz"
            subprocess.run(["tar", "--exclude-vcs", "-cJf", f"{BACKUPPATH}/{archive}", "-C", source, "."], check=True)
            
        else:
            return True, f"Unrecognized compression format on {name}"
            
        cPrint(f"Encrypting {name}...", "BLUE") if args.debug else None
        if os.path.exists(f"{BACKUPPATH}/{archive}.gpg"):
        	os.remove(f"{BACKUPPATH}/{archive}.gpg")
        subprocess.run(["gpg", "--symmetric", "--cipher-algo", "AES256", "--batch", "--passphrase", f"{CONF['backup']['password']}", "-o", f"{BACKUPPATH}/{archive}.gpg", f"{BACKUPPATH}/{archive}"], check=True)
        if os.path.exists(f"{BACKUPPATH}/{archive}"):
        	os.remove(f"{BACKUPPATH}/{archive}")

        return False, f"{archive} created and stored"
    except subprocess.CalledProcessError:
        return True, f"TAR command failed on {name}"

##############################################################################80
# Delete files older than the expiry period
##############################################################################80
def cleanUp(name, deleteAfter):
    cPrint(f"Deleting archives older than {deleteAfter} days...", "BLUE") if args.debug else None
    backup = f"{BACKUPPATH}/{name}"
    try:
        subprocess.run(["find", f"{backup}", "-type", "f", "-mtime", f"+{deleteAfter}", "-delete"], check=True)
        return False, f"Cleanup successful for {name}"
    except subprocess.CalledProcessError:
        return True, f"Cleanup failed on {name}"

##############################################################################80
# rClone to cloud storage
##############################################################################80
def rCloneToCloud():
    cPrint(f"rCloning to cloud storage...", "BLUE") if args.debug else None
    cloudPath = CONF["backup"]["cloudPath"] + HOSTNAME
    method = CONF["backup"]["rCloneMethod"] if "rCloneMethod" in CONF["backup"] else "copy"
    try:
        subprocess.run(["rclone", method, BACKUPPATH, cloudPath], check=True, capture_output=True)
        return False, "RClone sync successful"
    except subprocess.CalledProcessError:
        return True, "RClone sync failed"

##############################################################################80
# Begin main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None

    deleteAfter = CONF["backup"]["deleteAfter"]

    metrics = []
    for item in CONF["backup"]["items"]:
        name = item["name"]
        path = item["path"] if "path" in item else False

        metrics.append(createDirectory(name))

        if item["compress"] and not args.skipCompress:
            metrics.append(compress(name, path))

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
