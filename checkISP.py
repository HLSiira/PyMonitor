#!/usr/bin/env python3

import os, sys
import time
import json
import csv
import statistics
import subprocess

from datetime import datetime
from collections import namedtuple
from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")

def byteToHuman(bytes, to, bsize=1024):
    a = {"k": 1, "m": 2, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(bytes)
    return bytes / (bsize ** a[to])


def byteToBits(bytes, to, bsize=125):
    a = {"k": 1, "m": 1000, "g": 3, "t": 4, "p": 5, "e": 6}
    r = float(bytes)
    return round(bytes / (bsize * a[to]), 2)


daily_test = subprocess.Popen('/usr/bin/speedtest -f json', shell=True, stdout=subprocess.PIPE).stdout.read()
data = json.loads(daily_test.decode('utf-8'))

# f = open("samples/speedtest.json", "r")
# daily_test = f.read()
# data = json.loads(daily_test)

ping = str(round(data["ping"]["latency"], 2))
download = byteToBits(data["download"]["bandwidth"], "m")
upload = byteToBits(data["upload"]["bandwidth"], "m")

cPrint(f'P{ping}, D{download}, U{upload} - {data["result"]["id"]}')

header = ["DateTime", "Ping", "Download", "Upload"]

SpeedTest = namedtuple("SpeedTest", ("SCANID ping download upload"))

csvToday = f'/home/liam/Artemis/SpeedTest/daily/{time.strftime("%Y%m%d")}.csv'
csvAnnual = f'/home/liam/Artemis/SpeedTest/yearly/summary_{time.strftime("%Y")}.csv'

TODAY, HISTORY = [], []
TODAY.append(SpeedTest(SCANID, ping, download, upload))

try:
    if os.stat(csvToday).st_size != 0:
        with open(csvToday) as csvfile:
            readCSV = csv.reader(csvfile, delimiter="|")

            next(readCSV)

            for row in readCSV:
                row = [item.strip() for item in row]
                TODAY.append(SpeedTest(*row))
except:
    pass

with open(csvToday, "w") as csvfile:
    writer = csv.writer(csvfile)
    header = "{:^14} |{:^10} |{:^12} |{:^10}".format(*header).split("|", 0)
    writer.writerow(header)

    for speedtest in TODAY:
        speedtest = "{:^14} |{:>10} |{:>12} |{:>10}".format(*speedtest).split("|", 0)
        writer.writerow(speedtest)

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

    tooOld = time.time() - (90 * 7 * 86400) # 3 months ago
    path = "data/speedtest/daily"
    for f in os.listdir(path):
        f = os.path.join(path, f)
        if os.stat(f).st_mtime < tooOld and os.path.isfile(f):
            os.remove(f)

if True or float(download) < 400 or float(upload) < 20:
    speed = SpeedTest(SCANID, ping, download, upload)
    if DEBUG:
        print(speed)
    else:
        cPrint(f"Connection speeds outside of defined bounderies...Sending alert...")
        subject = f'ISP: P{ping}, D{download}, U{upload}'
        send("ISP Speed Alert", subject)
else:
    cPrint(f"Connection speeds within defined bounderies")
exit(0)
