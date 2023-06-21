#!/usr/bin/env python
# coding=utf-8

import re
from email.mime.text import MIMEText

from requests import get

current_ip = get('https://api.ipify.org').text
#print('My public IP address is:', current_ip)

if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",current_ip):
    print('IP Invalid:', current_ip)
    quit()

recorded_ip = ''

try:
    f = open("/home/liam/ipaddress", "r")
    recorded_ip = f.read()
    f.close()
except:
    pass

if current_ip != recorded_ip:
    f = open("/home/liam/ipaddress", "w")
    f.write(current_ip)

    print("Emailing new IP({}) address...".format(current_ip))

    msg = "Glenora IP Address has changed:\n"
    msg = msg + "Old IP Address: {}\n".format(recorded_ip)
    msg = msg + "New IP Address: {}\n".format(current_ip)
    msg = MIMEText(msg)

    msg["From"] = "Catalog879 <Catalog879@gmail.com>"
    msg["To"] = "Liam Siira <Liam@siira.io>"
    msg["Subject"] = "Alert: IP Address Change"
    p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
    p.communicate(msg.as_bytes())

else:
    print("IP({}) address...".format(current_ip))
