#!/usr/bin/env python3


# https://gist.github.com/yumminhuang/8b1502a49d8b20a6ae70

import os, sys
import subprocess

import apt
import apt_pkg

from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")

"""
Following functions are used to return package info of available updates.
See: /usr/lib/update-notifier/apt_check.py
"""
SYNAPTIC_PINFILE = "/var/lib/synaptic/preferences"
DISTRO = subprocess.check_output(
    ["lsb_release", "-c", "-s"], universal_newlines=True
).strip()


def clean(cache, depcache):
    """ unmark (clean) all changes from the given depcache """
    # mvo: looping is too inefficient with the new auto-mark code
    # for pkg in cache.Packages:
    #    depcache.MarkKeep(pkg)
    depcache.init()


def saveDistUpgrade(cache, depcache):
    """ this functions mimics a upgrade but will never remove anything """
    depcache.upgrade(True)
    if depcache.del_count > 0:
        clean(cache, depcache)
    depcache.upgrade()


def getAptUpdates():
    """
    Return a list of dict about package updates
    """
    comPacks = []

    apt_pkg.init()
    # force apt to build its caches in memory for now to make sure
    # that there is no race when the pkgcache file gets re-generated
    apt_pkg.config.set("Dir::Cache::pkgcache", "")

    try:
        cache = apt_pkg.Cache(apt.progress.base.OpProgress())
    except SystemError as e:
        sys.stderr.write("Error: Opening the cache (%s)" % e)
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
        saveDistUpgrade(cache, depcache)
    except SystemError as e:
        sys.stderr.write("Error: Marking the upgrade (%s)" % e)
        sys.exit(-1)

    # use assignment here since apt.Cache() doesn't provide a __exit__ method
    # on Ubuntu 12.04 it looks like
    # aptcache = apt.Cache()

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


def securityHelper(version):
    """ check if the given version is a security update (or masks one) """
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


def isSecurityUpgrade(pack, version):
    """ check if the given version is a security update (or masks one) """
    inst_ver = pack.current_ver

    if securityHelper(version):
        return True

    # now check for security updates that are masked by a
    # canidate version from another repo (-proposed or -updates)
    for ver in pack.version_list:
        if inst_ver and apt_pkg.version_compare(ver.ver_str, inst_ver.ver_str) <= 0:
            # print "skipping '%s' " % ver.VerStr
            continue
        if securityHelper(ver):
            return True

    return False


(comPacks, secCount) = getAptUpdates()
subject = f"{len(comPacks)}/{secCount} Updatable Package(s)"

if len(comPacks) < 1:
    cPrint("No package updates.")
    exit(0)
elif not DEBUG:
    cPrint(f"{subject}...Sending notification...")

sForm = "{:<24}| {:<16}| {:<16}\n"

text = sForm.format("Package Name", "Current Version", "Latest Version")
text += ("=" * 60) + "\n"
html = "<tr><th>Package Name</th><th>Current Version</th><th>Latest Version</th></tr>"

for pack in comPacks:
    pack["name"] = ("*" if pack["security"] else " ") + pack["name"]

    name = f'{pack["name"][:21]}...' if len(pack["name"]) > 24 else pack["name"]
    iVersion = pack["iVersion"][:17] if len(pack["iVersion"]) > 17 else pack["iVersion"]
    nVersion = pack["nVersion"][:17] if len(pack["nVersion"]) > 17 else pack["nVersion"]

    text += sForm.format(name, iVersion, nVersion)
    html += f"<tr><td>{name}</td><td>{iVersion}</td><td>{nVersion}</td></tr>"

html += f"<tr><td colspan=\"3\">* Updates for security packages</td></tr>"
text += "\n * Updates for security packages"

if DEBUG:
    print(text)
else:
    send("table", subject, text, html)

exit(0)