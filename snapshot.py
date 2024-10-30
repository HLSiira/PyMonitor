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
from utils import cPrint, getBaseParser, pingHealth, sendNotification, CONF, HOSTNAME

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Creates backups and sends to cloud storage using rClone.")
parser.add_argument("--noArchive", action="store_true", help="Skip creating tarbell archives.")
parser.add_argument("--noEncrypt", action="store_true", help="Skip encrypting tarbell archives.")
parser.add_argument("--noClean", action="store_true", help="Skip deleting older tarbell archives.")

parser.add_argument("--noDiff", action="store_true", help="Skip.")
parser.add_argument("--noPrune", action="store_true", help="Skip.")
args = parser.parse_args()

# Define valid compressions and the corresponding tar options
COMP_METHODS = {
    "gzip": (".gz", "-zcf"),   # Fastest, low compression
    "zstd": (".zst", "-zstd"), # Fast, medium compression
    "xz": (".xz", "-cJf")      # Slowest, highest compression
}

##############################################################################80
# Configuration Settings
##############################################################################80
ARCHS = CONF["backup"]["arch_path"]
DIFFS = CONF["backup"]["diff_path"]

def exec(cmd): return subprocess.run(cmd, check=True, capture_output=True)

##############################################################################80
# Create backup directory
##############################################################################80
def create_directory(name):
    cPrint(f"Creating directory for {name}...", "BLUE") if args.debug else None
    try:
        archive_path = f"{ARCHS}/{name}"
        if os.path.exists(archive_path):
            os.makedirs(archive_path, exist_ok=True)
            return 200, f"Directory creation successful: {name}"
        else:
            return 100, f"Directory already exists: {name}"
    except subprocess.CalledProcessError:
        return 400, f"Directory creation failed on {name}"

##############################################################################80
#
##############################################################################80
def create_archive(name, source, method="xz"):
    cPrint(f"Creating archive for {name}...", "BLUE") if args.debug else None

    try:
        if method not in COMP_METHODS:
            return 400, f"Unrecognized compression format: {name} ({method})"

        weeknum = datetime.now().strftime("%V")
        ext, flags = COMP_METHODS[method]
        archive = f"{name}/{name}-WK{weeknum}.tar{ext}"        

        cmd = ["tar", "--exclude-vcs", flags, f"{ARCHS}/{archive}", "-C", source, "."]
        exec(cmd)

        return 200, f"Tarbell archive created: {name}"
    except subprocess.CalledProcessError:
        return 400, f"TAR cmd failed: {name}"
        
##############################################################################80
#
##############################################################################80
def encrypt_archive(name, source, method="xz"):
    cPrint(f"Encrypting archive for {name}...", "BLUE") if args.debug else None
    try:
        if method not in COMP_METHODS:
            return 400, f"Unrecognized compression format: {name} ({method})"
        weeknum = datetime.now().strftime("%V")
        ext, flags = COMP_METHODS[method]
        archive = f"{name}/{name}-WK{weeknum}.tar{ext}"

        if os.path.exists(f"{ARCHS}/{archive}.gpg"):
            os.remove(f"{ARCHS}/{archive}.gpg")

        cmd = [
            "gpg", "--symmetric", "--cipher-algo", "AES256",
            "--batch", "--passphrase-file", "data/password",
            "-o", f"{ARCHS}/{archive}.gpg", f"{ARCHS}/{archive}",
        ]
        exec(cmd)

        if os.path.exists(f"{ARCHS}/{archive}"):
            os.remove(f"{ARCHS}/{archive}")

        return 200, f"Tarbell archive encrypted: {name}"
    except subprocess.CalledProcessError:
        return 400, f"Encryption failed: {name}"

##############################################################################80
# Delete files older than the expiry period
##############################################################################80
def clean_archive(name, deleteAfter):
    cPrint(f"Cleaning archives for {name}...", "BLUE") if args.debug else None

    try:
        archive_path = f"{ARCHS}/{name}"
        if not os.path.exists(archive_path):
            return 404, f"Cleanup failed on {name}; path missing"
        cPrint(f"Deleting archives older than {deleteAfter} days...", "BLUE") if args.debug else None
        cmd = ["find", f"{archive_path}", "-type", "f", "-mtime", f"+{deleteAfter}", "-delete"]
        exec(cmd)

        return 200, f"Archive cleanup successful: {name}"
    except subprocess.CalledProcessError:
        return 400, f"Archive cleanup failed: {name}"

##############################################################################80
#
##############################################################################80
def update_differential(name, source):
    cPrint(f"Creating differential on {name}...", "BLUE") if args.debug else None
    try:
        repo_path = f"{DIFFS}/{name}"
        # Backup cmd using Restic
        if not os.path.exists(repo_path):
            exec(["restic", "-r", repo_path, "init", "--password-file", "data/password"])

        cmd = ["restic", "-r", repo_path, "backup", source, "--password-file", "data/password"]
        exec(cmd)
        return 200, f"Differential backup successful: {name}"
    except subprocess.CalledProcessError:
        return 400, f"Differential backup failed: {name}"

##############################################################################80
# Delete files older than the expiry period
##############################################################################80
def prune_differential(name, deleteAfter):
    cPrint(f"Pruning up differentials for {name}...", "BLUE") if args.debug else None

    try:
        differential_path = f"{DIFFS}/{name}"
        cmd = [
            "restic", "-r", differential_path,
            "forget", "--keep-daily", deleteAfter, "--prune",
        #         "--keep-daily", "30",
        #         "--keep-weekly", "4",
        #         "--keep-monthly", "12",
            "--password-file", "data/password"
        ]
        exec(cmd)
        return 200, f"Differential pruned: {name}"
    except subprocess.CalledProcessError:
        return 400, f"Cleanup failed on {name}"

##############################################################################80
# rClone to cloud storage
##############################################################################80
def rCloneToCloud():
    cPrint(f"rCloning to cloud storage...", "BLUE") if args.debug else None
    try:
        cloud_path = CONF["backup"]["cloud_path"] + HOSTNAME
        method = CONF["backup"]["rCloneMethod"] if "rCloneMethod" in CONF["backup"] else "copy"
        exec(["rclone", method, ARCHS, f"{cloud_path}/archs"])
        exec(["rclone", method, DIFFS, f"{cloud_path}/diffs"])
        return 200, "RClone sync successful"
    except subprocess.CalledProcessError:
        return True, "RClone sync failed"

##############################################################################80
# Begin main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None

    deleteAfter = CONF["backup"]["deleteAfter"]

    metrics = []
    for name, info in CONF["backup"]["items"].items():
        path = info["path"] if "path" in info else False

        metrics.append(create_directory(name))

        if "tar" in info["steps"] and not args.noArchive:
            metrics.append(create_archive(name, path))

        if "enc" in info["steps"] and not args.noEncrypt:
            metrics.append(encrypt_archive(name, deleteAfter))

        if "cln" in info["steps"] and not args.noClean:
            metrics.append(clean_archive(name, deleteAfter))
            
        if "dif" in info["steps"] and not args.noDiff:
            metrics.append(update_differential(name, path))

        if "prn" in info["steps"] and not args.noPrune:
            metrics.append(update_differential(name, path))


    metrics.append(rCloneToCloud())

    message = "<b>Process status:</b>"
    sendNotice = False

    for status, text in metrics:
        if status > 299:
            sendNotice = True
        message += f"\n\t- {text}"

    if sendNotice or args.test:
        cPrint(f"Error in backup process, sending notification...", "RED")
        subject = "Error in backup process"

        sendNotification(subject, message)
    else:
        cPrint("Backup successful.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)


if __name__ == "__main__":
    main()
