#!/usr/bin/env python3

import os, sys
import time
import json
import csv
import statistics
import subprocess

from datetime import datetime
from collections import namedtuple
from utils import hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")
GENFILE = hasFlag("g")

# Header at the top of every CSV
dailyHeader = ["Hour", "DateTime", "Ping", "Download", "Upload", "TestID"]
yearlyHeader = ["Day", "DateTime", "Ping", "Download", "Upload"]

# Directory of data location, use trailing "/"
dataLocation = ""

# File path of today's speed tests
csvToday = f'{dataLocation}daily/{time.strftime("%m-%d")}.csv'

# File path of the annual CSV file
csvYearly = f'{dataLocation}yearly/{time.strftime("%y")}.csv'


def byteToHuman(bytes, to, bsize=1024):
    a = {"k": 1, "m": 2, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(bytes)
    return bytes / (bsize ** a[to])


def byteToBits(bytes, to, bsize=125):
    a = {"k": 1, "m": 1000, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(bytes)
    return round(bytes / (bsize * a[to]), 2)


# Function that formats the rows visually how I like them within a CSV File
def rowFormat(text):
    # Yearly CSV only has 5 columns
    if len(text) == 5:
        return "{:^5} |{:^14} |{:^10} |{:^12} |{:^10}".format(*text).split("|", 0)

    # Daily CSV has 6 columns
    else:
        return "{:^5} |{:^14} |{:^10} |{:^12} |{:^10} |{:^32}".format(*text).split("|", 0)

# Generate a blank file for daily tests
def genDailyFile(path):
    with open(path, "w") as csvfile:
        # Open/create the csvFile writer
        writer = csv.writer(csvfile)

        # Add the header
        writer.writerow(rowFormat(dailyHeader))

        for row in range(24):
            writer.writerow(rowFormat([row + 1, 0, 0, 0, 0, 0]))
                
        writer.writerow(rowFormat(["AVG", 0, 0, 0, 0, "Unused"]))

# Generate a blank file for yearly tests
def genYearlyFile(path):
    with open(path, "w") as csvfile:
        # Open/create the csvFile writer
        writer = csv.writer(csvfile)

        # Add the header
        writer.writerow(rowFormat(dailyHeader))

        for row in range(365):
            writer.writerow(rowFormat([row + 1, 0, 0, 0, 0]))
                
        writer.writerow(rowFormat(["AVG", 0, 0, 0, "Unused"]))

# Read from CSV into Tuple Array
def readCSV(path, testTuple):
    temp = []
    with open(path) as csvfile:
        readCSV = csv.reader(csvfile, delimiter="|")
        for row in readCSV:
            temp.append(testTuple(*row))
    return temp

# Create the daily and yearly files if they don't exist already
if GENFILE or not os.path.isfile(csvToday):
    if DEBUG:
        print("Generating daily file")
    genDailyFile(csvToday)

if GENFILE or not os.path.isfile(csvYearly):
    if DEBUG:
        print("Generating yearly file")
    genYearlyFile(csvYearly)


# Tuple representing hourly test
testHourly = namedtuple("testHourly", ("hour datetime ping download upload testID"))
testDaily = namedtuple("testHourly", ("day datetime ping download upload"))

testsToday = readCSV(csvToday, testHourly)
testsYearly = readCSV(csvYearly, testDaily)

results = False
if hasFlag("n"):
    # Pull from a sample JSON
    f = open("speedtest.json", "r")
    test = f.read()
    results = json.loads(test)
else:
    # Run speedtest-cli and use live data
    test = subprocess.Popen('/usr/bin/speedtest -f json', shell=True, stdout=subprocess.PIPE).stdout.read()
    results = json.loads(test.decode('utf-8'))

# Early exit if something is wrong with the data
if not results:
    cPrint("Error in retrieving data")
    exit(1)


ping = str(round(results["ping"]["latency"], 2))
download = byteToBits(results["download"]["bandwidth"], "m")
upload = byteToBits(results["upload"]["bandwidth"], "m")
testID = results["result"]["id"]

cPrint(f'P{ping}, D{download}, U{upload} - {testID}')

exit(0)

# Generate arrays for Today's tests and the yearly
TODAY.append(SpeedTest(SCANID, ping, download, upload, testID))



with open(csvToday, "w") as csvfile:
    writer = csv.writer(csvfile)
    header = "{:^14} |{:^10} |{:^12} |{:^10}".format(*header).split("|", 0)
    writer.writerow(header)

    for speedtest in TODAY:
        speedtest = "{:^14} |{:>10} |{:>12} |{:>10}".format(*speedtest).split("|", 0)
        writer.writerow(speedtest)

exit(0)

if DEBUG or int(time.strftime("%H")) >= 23:

    Summary = namedtuple(
        "Summary",
        (
            "date average_ping lowest_download average_download highest_download lowest_upload average_upload highest_upload"
        ),
    )

    SUMMARY = Summary(
        time.strftime("%m-%d"),
        round(statistics.mean([float(test.ping) for test in TODAY]), 2),
        round(min([float(test.download) for test in TODAY]), 2),
        round(statistics.mean([float(test.download) for test in TODAY]), 2),
        round(max([float(test.download) for test in TODAY]), 2),
        round(min([float(test.upload) for test in TODAY]), 2),
        round(statistics.mean([float(test.upload) for test in TODAY]), 2),
        round(max([float(test.upload) for test in TODAY]), 2),
    )
    SUMMARY
    SUMMARY = [
        SUMMARY.date,
        SUMMARY.average_ping,
        f"{SUMMARY.lowest_download}/{SUMMARY.average_download}/{SUMMARY.highest_download}",
        f"{SUMMARY.lowest_upload}/{SUMMARY.average_upload}/{SUMMARY.highest_upload}",
    ]

    HISTORY.append(SUMMARY)

    try:
        if os.stat(csvAnnual).st_size >= 0:
            with open(csvAnnual) as csvfile:
                readCSV = csv.reader(csvfile, delimiter="|")

                next(readCSV)
                for row in readCSV:
                    HISTORY.append(row)
    except:
        pass

    with open(csvAnnual, "w") as csvfile:

        writer = csv.writer(csvfile)

        header = [
            "Date",
            "Avg Ping(ms)",
            "Download Speeds(Mb/s)",
            "Upload Speeds(Mb/s)",
        ]
        header = "{:^7}|{:>12}|{:>22}|{:>20}".format(*header)

        writer.writerow(header.split("|", 0))

        for speedtest in HISTORY:
            speedtest = "{:^7}|{:^12}|{:^22}|{:^20}".format(*speedtest)
            writer.writerow(speedtest.split("|", 0))

if float(download) < 60 or float(upload) < 5:
    speed = SpeedTest(SCANID, ping, download, upload)
    if DEBUG:
        print(speed)
    else:
        cPrint(f"Connection speeds outside of defined bounderies...Sending alert...")
else:
    cPrint(f"Connection speeds within defined bounderies")
exit(0)
