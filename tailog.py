#!/usr/bin/python3

"""
Description:
    A log file curtailer, used to manage log sizes for custom commands. High performance not guaranteed with marge maximum ceilings.

Usage:
    Line Mode: echo -ne "$(date)\n" | ./tailog.py -lm 100 -f cron.log
    Byte Mode: echo -ne "$(date)\n" | ./tailog.py -bm 500 -f cron.log
"""


from sys import stdin
import os
import argparse

parser = argparse.ArgumentParser(description="Create a tailog.")

parser.add_argument("-f", dest="path", metavar="FilePath", type=str, default='data/cron.log', help="the path of the tailog to be created")
parser.add_argument('-m', dest='ceil', metavar='MAXSIZE', type=int, default=100, help='the byte/line limit to the tailog to (default 100)')

group = parser.add_mutually_exclusive_group()
group.add_argument('-l', dest='mode', action='store_const', const='line', help='limit the log by line count', default='line')
group.add_argument('-b', dest='mode', action='store_const', const='byte', help='limit the log by byte count')

args = parser.parse_args()

(maximum, logpath, mode) = args.ceil, args.path, args.mode

# Get absolute path of the log file
if not os.path.isabs(logpath):
    dname = os.getcwd()
    logpath = os.path.join(dname, logpath)
logpath = os.path.abspath(logpath)

if not os.path.exists(logpath):
    open(logpath, "a").close()


# Append stdin to the current log file and close the write process
logfile = open(logpath, "a")
for line in stdin:
    logfile.write(line)
logfile.close()

logsize = 0

# Determine size of the file, either by line or byte
if mode == "line":
    # line mode
    logfile = open(logpath)

    with logfile as f:
        for i, l in enumerate(f):
            pass
    logsize = i + 1

elif mode == "byte":
    logsize = os.path.getsize(logpath)

# Early exit if Log File does not exceed the maximum limit
if logsize <= maximum:
    exit(0)

# Log file too large, create a temporary file to hold the curtailed log data
tempath = f"{logpath}.temp"
if not os.path.exists(tempath):
    open(tempath, "a").close()

# Read the log file, and start writing to the temp log once the offset is reached
# offset representing the old data that needs to be curtailed
offset = logsize - maximum
if mode == "line":
    temfile = open(tempath, "a")
    lines = iter(open(logpath))
    for _ in range(offset):
        next(lines)
    temfile.writelines(lines)

elif mode == "byte":
    temfile = open(tempath, "wb")
    logfile = open(logpath, "rb")
    logfile.seek(offset)
    temfile.write(logfile.read())

# Close the tempfile and replace the log file with the temporary file
temfile.close()
os.remove(logpath)
os.rename(tempath, logpath)
os.chmod(logpath, 0o770)
exit(0)
