#!/usr/bin/env python3

##############################################################################80
# ISP Speed Monitor 20231227
##############################################################################80
# Description: Check ISP speeds and maintains human-readable records, sends
# notifications via PushOver if speeds are outside of defined bounderies.
# Usage via CRON: (Runs every hour on minute four)
#   4 * * * * cd /path/to/folder && ./checkISP.py --cron 2>&1 | ./tailog.py
# Usage via CLI:
#   cd /path/to/folder && ./checkISP.py (-cdnqrt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -n: use generated scan instead of running speedtest.
#           -q: disables push notifications, prints message to terminal.
#           -r: recalculates all summaries for current year.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import os, sys
import time
import json
import csv
import statistics
import subprocess
import glob
import re

from datetime import datetime
from collections import namedtuple
from utils import cPrint, getBaseParser, pingHealth, sendNotification, SCANID, CONF

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Runs and stores speedtest of ISP.")
parser.add_argument(
    "-n",
    "--noscan",
    action="store_true",
    help="use generated scan instead of running speedtest.",
)
parser.add_argument(
    "-r",
    "--recalc",
    action="store_true",
    help="Recalculates all summaries for current year.",
)
args = parser.parse_args()

SpeedTest = namedtuple("SpeedTest", ("DateTime Ping Download Upload"))
DailySummary = namedtuple(
    "DailySummary", ("Date AvgPing MinDown AvgDown MaxDown MinUp AvgUp MaxUp")
)

##############################################################################80
# Configurations
##############################################################################80
storagePath = CONF["speedTest"]["storagePath"]


##############################################################################80
# Run the speed test and return results
##############################################################################80
def runSpeedTest():
    cPrint("Running speed test...", "BLUE") if args.debug else None
    if args.noscan:
        return {
            "ping": {"latency": 9.972},
            "download": {"bandwidth": 68768535},
            "upload": {"bandwidth": 2983970},
            "result": {"id": "Generated"},
        }
    try:
        result = subprocess.run(
            "/usr/bin/speedtest -f json", shell=True, stdout=subprocess.PIPE
        )
        return json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        cPrint("Error decoding speed test results.", "RED")
        sys.exit(1)


##############################################################################80
# Helper: Convert bytes to Megabits.
##############################################################################80
def byteToMbits(bytes):
    return round(bytes * 8 / 10**6, 2)


##############################################################################80
# Process current test into database and save to CSV file.
##############################################################################80
def processCurrentTest(currentTest, date):
    cPrint("Processing hourly test...", "BLUE") if args.debug else None
    csvToday = f"{storagePath}/daily/{date}.csv"
    allTests = []

    # Read from CSV file all previous tests
    if os.path.exists(csvToday) and os.stat(csvToday).st_size > 0:
        with open(csvToday, mode="r") as reader:
            # Create a DictReader, and then strip whitespace from the field names
            readCSV = csv.DictReader(
                (line.replace("\0", "") for line in reader), delimiter="|"
            )
            readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

            for row in readCSV:
                cleanedRow = {k: v.strip() for k, v in row.items()}
                allTests.append(SpeedTest(**cleanedRow))

    # Append today's test
    allTests.append(currentTest)

    # Save all tests to CSV file
    header = currentTest._fields
    header = "{:^14}|{:^6}|{:^8}|{:^8}".format(*header).split("|", 0)

    with open(csvToday, "w", newline="") as writer:
        writeCSV = csv.writer(writer)
        writeCSV.writerow(header)

        # Write data rows
        for test in allTests:
            test = "{:^14}|{:>5} | {:<7}|{:>7}".format(*test).split("|", 0)
            writeCSV.writerow(test)

    return allTests


##############################################################################80
# Process current test into database and save to CSV file.
##############################################################################80
def createSummary(todaysTests, date):
    sumPing, sumDownload, sumUpload = 0, 0, 0
    minDownload, maxDownload = float("inf"), float("-inf")
    minUpload, maxUpload = float("inf"), float("-inf")
    numTests = len(todaysTests)

    for test in todaysTests:
        ping = float(test.Ping)
        download = float(test.Download)
        upload = float(test.Upload)

        sumPing += ping
        sumDownload += download
        sumUpload += upload

        minDownload = min(download, minDownload)
        maxDownload = max(download, maxDownload)

        minUpload = min(upload, minUpload)
        maxUpload = max(upload, maxUpload)

    # Calculate averages and create the summary namedtuple.
    averagePing = round(sumPing / numTests, 2) if numTests > 0 else 0
    averageDownload = round(sumDownload / numTests, 2) if numTests > 0 else 0
    averageUpload = round(sumUpload / numTests, 2) if numTests > 0 else 0

    summary = DailySummary(
        date,
        averagePing,
        round(minDownload, 2),
        averageDownload,
        round(maxDownload, 2),
        round(minUpload, 2),
        averageUpload,
        round(maxUpload, 2),
    )

    return summary


##############################################################################80
# Process current test into database and save to CSV file.
##############################################################################80
def saveTodaysSummary(todaysSummary):
    cPrint("Processing todays test...", "BLUE") if args.debug else None
    csvAnnual = f"{storagePath}/summaries/{time.strftime('%Y')}.csv"

    allSummaries = []

    # Read from CSV file all previous tests
    if os.path.exists(csvAnnual) and os.stat(csvAnnual).st_size > 0:
        with open(csvAnnual, mode="r") as reader:
            # Create a DictReader, and then strip whitespace from the field names
            readCSV = csv.DictReader(
                (line.replace("\0", "") for line in reader), delimiter="|"
            )
            readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

            for row in readCSV:
                cleanedRow = {k: v.strip() for k, v in row.items()}
                rowSummary = DailySummary(**cleanedRow)
                if rowSummary.Date != todaysSummary.Date:
                    allSummaries.append(rowSummary)

    # Read from CSV file all previous tests
    allSummaries.append(todaysSummary)

    # Save all tests to CSV file
    header = todaysSummary._fields
    header = "{:^10}|{:^7}|{:^8}|{:^8}|{:^8}|{:^8}|{:^8}|{:^8}".format(*header).split(
        "|", 0
    )

    with open(csvAnnual, "w", newline="") as writer:
        writeCSV = csv.writer(writer)
        writeCSV.writerow(header)

        # Write data rows
        for test in allSummaries:
            test = "{:^10}|{:>6} | {:<7}| {:<7}| {:<7}| {:<7}| {:<7}|{:>7}".format(
                *test
            ).split("|", 0)
            writeCSV.writerow(test)


##############################################################################80
# Process current test into database and save to CSV file.
##############################################################################80
def recalcAllSummaries(year):
    cPrint("Recalculating all summaries...", "BLUE") if args.debug else None
    csvAnnual = f"{storagePath}/summaries/{year}.csv"
    dailyFolder = f"{storagePath}/daily/"

    allSummaries = []

    # for root, dirs, files in os.walk(dailyFolder):
    pattern = f"{year}*.csv"  # Pattern for files like '2023xxxx.csv'
    for dailyPath in glob.glob(os.path.join(dailyFolder, pattern)):
        # Read from CSV file all previous tests
        if os.stat(dailyPath).st_size == 0:
            continue

        allTests = []
        date = re.search(r"(\d{4}\d{2}\d{2})", dailyPath).group(1)

        with open(dailyPath, mode="r") as reader:
            # Create a DictReader, and then strip whitespace from the field names
            readCSV = csv.DictReader(
                (line.replace("\0", "") for line in reader), delimiter="|"
            )
            readCSV.fieldnames = [name.strip() for name in readCSV.fieldnames]

            for row in readCSV:
                cleanedRow = {k: v.strip() for k, v in row.items()}
                allTests.append(SpeedTest(**cleanedRow))

        currentSummary = createSummary(allTests, date)
        allSummaries.append(currentSummary)

    allSummaries = sorted(allSummaries, key=lambda x: x.Date)

    # Save all tests to CSV file
    header = allSummaries[0]._fields
    header = "{:^10}|{:^7}|{:^8}|{:^8}|{:^8}|{:^8}|{:^8}|{:^8}".format(*header).split(
        "|", 0
    )

    with open(csvAnnual, "w", newline="") as writer:
        writeCSV = csv.writer(writer)
        writeCSV.writerow(header)

        # Write data rows
        for test in allSummaries:
            test = "{:^10}|{:>6} | {:<7}| {:<7}| {:<7}| {:<7}| {:<7}|{:>7}".format(
                *test
            ).split("|", 0)
            writeCSV.writerow(test)

    return allSummaries


##############################################################################80
# Begin main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None

    currentTest = runSpeedTest()
    ping = round(currentTest["ping"]["latency"], 2)
    download = byteToMbits(currentTest["download"]["bandwidth"])
    upload = byteToMbits(currentTest["upload"]["bandwidth"])

    cPrint(f"P{ping}, D{download}, U{upload} - {currentTest['result']['id']}")

    currentTest = SpeedTest(SCANID, ping, download, upload)

    date = time.strftime("%Y%m%d")
    todaysTests = processCurrentTest(currentTest, date)
    todaysSummary = createSummary(todaysTests, date)
    if args.recalc:
        recalcAllSummaries(time.strftime("%Y"))
    else:
        saveTodaysSummary(todaysSummary)

    if (
        float(download) < CONF["speedTest"]["minDownload"]
        or float(upload) < CONF["speedTest"]["minUpload"]
        or args.test
    ):
        cPrint("Speeds outside of boundaries, sending notification...", "RED")
        subject = f"ISP Speed Alert"
        message = f"ISP: P{ping}, D{download}, U{upload}"

        sendNotification(subject, message, ttl=600)
    else:
        cPrint("Speeds within defined boundaries.", "BLUE")

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    pingHealth()
    sys.exit(0)


if __name__ == "__main__":
    main()
