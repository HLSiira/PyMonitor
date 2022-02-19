#!/usr/bin/env python3

import os, sys
import socket

from subprocess import Popen, PIPE
from datetime import datetime

host = socket.gethostname().upper()
name = os.path.basename(sys.argv[0])

# SCANID is also the date/time
SCANID = datetime.now().strftime("%Y%m%d%H%M")

def cPrint(msg):
    print(f"{name}: {SCANID} {msg}")

def hasFlag(flg):
    return len(sys.argv) > 1 and flg in sys.argv[1]
