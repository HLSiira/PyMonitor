#!/usr/bin/env python3

import psutil
from utils import send, hasFlag, cPrint, SCANID

DEBUG = hasFlag("d")
subject = "System Health Warning"

def checkCPU(threshold=85):
    usage = psutil.cpu_percent(interval=1)
    if usage > threshold or DEBUG:
        return f"High CPU usage: {usage}%"
    return False

def checkMemory(threshold=75):
    memory = psutil.virtual_memory()
    memory = memory.used / memory.total * 100
    if memory > threshold or DEBUG:
        return f"High memory usage: {memory:.2f}%"
    return False

def checkStorage(threshold=80):
    storage = psutil.disk_usage('/')
    storage = storage.used / storage.total * 100
    if storage > threshold or DEBUG:
        return f"High disk usage: {storage:.2f}%"
    return False

alerts = [checkCPU(), checkMemory(), checkStorage()]

if any(alerts):
    message = "\n".join(alerts)
    cPrint(f"{subject}, sending notification...")
    
    if DEBUG:
        print(message)
    else:
        send(subject, message)

exit(0)
