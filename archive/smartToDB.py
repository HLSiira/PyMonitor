#!/usr/bin/env python

""" store S.M.A.R.T. values in a database
    I should consider to record all SMART parameters.
    This python script has to be run as root! You may set it up as a cron job (to be run every hour) using crontab:
    sudo crontab -e
    0 * * * * /home/pklaus/b/smartToDB.py
"""

# Source: https://gist.github.com/pklaus/cfd9719cfd4073cc3d73/forks

import sqlite3
from os import remove, listdir, WEXITSTATUS, path, makedirs, geteuid
from commands import getstatusoutput
from re import search
from shlex import shlex
import sys
from datetime import datetime
import pdb

__author__ = "Philipp Klaus"
__copyright__ = "Copyright 2015 Philipp Klaus"
__credits__ = ""
__license__ = "GPL"
__version__ = "2.0"
__maintainer__ = ""
__email__ = "philipp.klaus AT gmail.com"
__status__ = "Development"  # Prototype Production

DATABASE_FILE = path.expanduser("~root/.smartToDB/smartToDB.sqlite")


def main(*args):
    if geteuid() != 0:
        print("You must be root to run this script.")
        sys.exit(1)
    connect_db()
    # now query S.M.A.R.T. status and insert new datasets to the DB:
    for drive in [
        dev for dev in listdir("/dev/") if search("^[hs]d.$", dev) != None
    ]:  # can also done with filter()... see commit 26c34437bbe4663547fed08202b08d8ca97ed783
        # insert_smart(drive)
        drive = "/dev/" + drive
        # absolute path for smartctl (for compatibility reasons with cron). See "It works from the command line but not in crontab" on http://www.unix.com/answers-frequently-asked-questions/13527-cron-crontab.html
        (status, txt) = getstatusoutput("/usr/sbin/smartctl -a -d ata " + drive)
        # print WEXITSTATUS(status) #exit status of command
        if WEXITSTATUS(status) == 2:
            print("Please run " + args[0] + " script as root.")
            sys.exit(1)
        temperature, seek_error_rate = 0, 0
        for line in txt.split("\n"):
            status_splitter = shlex(
                line, posix=True
            )  # we need shlex here instead of .split(" ") as the string is separated by MULTIPLE spaces.
            status_splitter.whitespace_split = True
            if search("^194 ", line):
                temperature = int(list(status_splitter)[9])
            if search("^  7 ", line):
                seek_error_rate = int(list(status_splitter)[9])
        insert_smart((drive, datetime.now(), temperature, seek_error_rate))


def create_initial_database(db):
    curs = db.cursor()
    # Create
    curs.execute(
        "CREATE TABLE smart (id INTEGER PRIMARY KEY, drive_address TEXT, time TIMESTAMP , temperature INTEGER, seek_error_rate INTEGER)"
    )
    db.commit()
    return db


def connect_db():
    try:
        open(DATABASE_FILE)
        db = sqlite3.connect(
            DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
    except:
        if not path.exists(path.split(DATABASE_FILE)[0]):
            makedirs(path.split(DATABASE_FILE)[0])
        db = sqlite3.connect(
            DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        create_initial_database(db)
        print("created inital database.")
    # "detect_...": to use the default adapters for datetime.date and datetime.datetime see http://docs.python.org/library/sqlite3.html#default-adapters-and-converters
    return db


def insert_smart(drive):
    conn = connect_db()
    curs = conn.cursor()
    # structure of table ta: id INTEGER PRIMARY KEY, drive_address TEXT, time TIMESTAMP , temperature REAL, seek_errors INTEGER
    curs.execute("INSERT INTO smart VALUES (NULL,?,?,?,?)", drive)
    conn.commit()


def delete_db():
    try:
        remove(DATABASE_FILE)
    except:
        print("error while trying to delete sqlite database " + DATABASE_FILE)


def get_all_datasets():
    curs = connect_db().cursor()
    curs.execute("SELECT * from smart")
    return curs


def print_all_datasets():
    for ds in get_all_datasets():
        print(ds)


if __name__ == "__main__":
    main(*sys.argv)
