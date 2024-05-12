#!/usr/bin/env python3

##############################################################################80
#
##############################################################################80
# Description:
#
# Usage via CRON: (Runs every day at 0703)
#   3 7 * * * cd /path/to/folder && ./checkIP4.py --cron 2>&1 | ./tailog.py
# Usage via CLI:
#   cd /path/to/folder && ./checkIP4.py (-cdqt)
#   Flags:  -c: Formats messages into loggable format, with more information.
#           -d: activates debug messages during run, to track progress.
#           -q: disables push notifications, prints message to terminal.
#           -t: overrides passing conditions to test notifications.
##############################################################################80
# Copyright (c) Liam Siira (www.siira.io), distributed as-is and without
# warranty under the MIT License. See [root]/LICENSE.md for more.
##############################################################################80

import sys, re, requests
from utils import getBaseParser, cPrint, sendNotification, CONF

##############################################################################80
# Global variables
##############################################################################80
parser = getBaseParser("Sends notification based on input stream.")
parser.add_argument(
    "-s", "--service", help="Name of the calling service", default="Unknown Service"
)
parser.add_argument("message", nargs="+", help="The message to send")
args = parser.parse_args()


##############################################################################80
# Being Main execution
##############################################################################80
def main():
    cPrint(f"Beginning main execution...", "BLUE") if args.debug else None

    subject = f"{args.service} Alert"
    message = " ".join(args.message)
    # message = sys.argv[1:]

    sendNotification(subject, message)

    cPrint(f"\t...complete!!!", "BLUE") if args.debug else None
    sys.exit(0)


if __name__ == "__main__":
    main()
