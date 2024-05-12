#!/usr/bin/env python3

##############################################################################80
# Apt Update Notifications 20231227
##############################################################################80
# Description: Check for package updates in a Debian-based system, categorizing
# them into regular and security updates, sends notifications via PushOver
# Usage via CRON: (Runs every day at 0701)
#   1 7 * * * cd /path/to/folder && ./checkAPT.py --cron 2>&1 | ./tailog.py
# Usage via CLI:
#   cd /path/to/folder && ./checkAPT.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import os, sys, subprocess
import apt, apt_pkg
from utils import cPrint, getBaseParser, pingHealth, sendNotification

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Sends notifications when package updates are available.")
args = parser.parse_args()

SYNAPTIC_PINFILE = "/var/lib/synaptic/preferences"
DISTRO = subprocess.check_output(
    ["lsb_release", "-c", "-s"], universal_newlines=True
).strip()


##############################################################################80
# Helper: Create a package url to send in the notification
##############################################################################80
def create_package_url(package_name):
    base_url = "https://packages.ubuntu.com/search?keywords="
    return f"{base_url}{package_name}"

##############################################################################80
# Check for package updates
##############################################################################80
def getAptUpdates():
    cPrint("Checking for package updates...", "BLUE") if args.debug else None
    
    comPacks = []

    apt_pkg.init()
    apt_pkg.config.set("Dir::Cache::pkgcache", "")

    try:
        cache = apt_pkg.Cache(apt.progress.base.OpProgress())
    except SystemError as e:
        cPrint(f"Error opening the cache: {e}", "RED")
        sys.exit(-1)

    depcache = apt_pkg.DepCache(cache)
    # read the pin files
    depcache.read_pinfile()
    # read the synaptic pins too
    if os.path.exists(SYNAPTIC_PINFILE):
        depcache.read_pinfile(SYNAPTIC_PINFILE)
    # init the depcache
    depcache.init()

    try:
        depcache.upgrade(True)
        if depcache.del_count > 0:
            depcache.init()
        depcache.upgrade()
    except SystemError as e:
        cPrint(f"Error marking the upgrade: {e}", "RED")
        sys.exit(-1)

    secCount = 0

    for pack in cache.packages:
        if not (depcache.marked_install(pack) or depcache.marked_upgrade(pack)):
            continue

        inst_ver = pack.current_ver
        cand_ver = depcache.get_candidate_ver(pack)
        if cand_ver == inst_ver:
            continue
        isSecPack = isSecurityUpgrade(pack, cand_ver)
        if isSecPack:
            secCount += 1

        record = {
            "name": pack.name,
            "security": isSecPack,
            # "section": pkg.section,
            "iVersion": inst_ver.ver_str if inst_ver else "-",
            "nVersion": cand_ver.ver_str if cand_ver else "-",
            "priority": cand_ver.priority_str,
        }
        comPacks.append(record)

    return comPacks, secCount

##############################################################################80
# Helper: Parses out security information
##############################################################################80
def securityHelper(version):
    security_pockets = [
        ("Ubuntu", "%s-security" % DISTRO),
        ("gNewSense", "%s-security" % DISTRO),
        ("Debian", "%s-updates" % DISTRO),
    ]

    for (file, index) in version.file_list:
        for origin, archive in security_pockets:
            if file.archive == archive and file.origin == origin:
                return True
    return False

##############################################################################80
# Check if package update is security related
##############################################################################80
def isSecurityUpgrade(pack, version):
    cPrint("Checking if package is security related...", "BLUE") if args.debug else None
    inst_ver = pack.current_ver

    if securityHelper(version):
        return True

    # now check for security updates that are masked by a
    # canidate version from another repo (-proposed or -updates)
    for ver in pack.version_list:
        if inst_ver and apt_pkg.version_compare(ver.ver_str, inst_ver.ver_str) <= 0:
            continue
        if securityHelper(ver):
            return True

    return False

##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint("Beginning main execution...", "BLUE") if args.debug else None

    (comPacks, secCount) = getAptUpdates()

    subject, message = "", ""

    if any(comPacks) or args.test:
        cPrint("APT Updates found, sending notification....", "BLUE")
        subject = f"{len(comPacks)}/{secCount} Updatable Package(s)"
        message = "<b>Packages:</b>"
        
        for pack in comPacks:
            url = create_package_url(pack["name"])
            name = f"{pack['name'][:21]}..." if len(pack["name"]) > 24 else pack["name"]
            if pack["security"]:
                message += f"\n\t- <font color='#ff4d3e'>{name}</font>"
            else:
                message += f"\n\t- {name}"
        
        sendNotification(subject, message)
    else:
        cPrint("No package updates.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)

if __name__ == "__main__":
    main()