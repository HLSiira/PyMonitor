#!/usr/bin/env python3

# Use to inline: https://www.campaignmonitor.com/resources/tools/css-inliner/
# Use to test emails: https://app.postdrop.io/
# Use to check email: https://www.htmlemailcheck.com/check/
import os, sys
import socket

from subprocess import Popen, PIPE
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# sudo pip3 install premailer
from premailer import transform


host = socket.gethostname().title()
name = os.path.basename(sys.argv[0])

desc = "Automated emails are carefully planned emails to be sent to subscribers at specific time intervals or as a response to the actions of users on a particular website. These emails can be sent individually or as part of a drip email campaign."

# SCANID is also the date/time
SCANID = datetime.now().strftime("%Y%m%d%H%M")

def cPrint(msg):
    print(f"{name}: {SCANID} {msg}")

def hasFlag(flg):
    return len(sys.argv) > 1 and flg in sys.argv[1]

def send(template, subject, text, html = None):
    if not hasFlag("k") and False:
        logo = open(f"data/logo.png.htm").read()
        msg = MIMEMultipart("alternative")
    
        wrapper = open(f"templates/wrapper.html").read()
        body = open(f"templates/{template}.html").read()
        
        wrapper = wrapper.replace("{subject}", subject)
        wrapper = wrapper.replace("{host}", host)
        wrapper = wrapper.replace("{logo}", logo)
        wrapper = wrapper.replace("{body}", body)
        wrapper = wrapper.replace("{desc}", desc)
    
        if template == "code":
            text = str(text)
            wrapper = wrapper.replace("{text}", text)
        elif template == "table":
            text = str(text)
            wrapper = wrapper.replace("{table}", html or text)
        elif template == "update":
            wrapper = wrapper.replace("{key1}", text["key1"])
            wrapper = wrapper.replace("{val1}", text["val1"])
            wrapper = wrapper.replace("{key2}", text["key2"])
            wrapper = wrapper.replace("{val2}", text["val2"])
        elif template == "speed":
            wrapper = wrapper.replace("{ping}", str(text.ping))
            wrapper = wrapper.replace("{upload}", str(text.upload))
            wrapper = wrapper.replace("{download}", str(text.download))
        else:
            exit(1)
            
        html = transform(wrapper)
    
        # Record the MIME types of both parts - text/plain and text/html.
        part1 = MIMEText(str(text), "plain")
        part2 = MIMEText(html, "html")
    
        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        msg.attach(part1)
        msg.attach(part2)
    
        msg["From"] = "Catalog879 <Catalog@pearwasps.io>"
        msg["To"] = "Liam Siira <Liam@siira.io>"
        msg["Subject"] = host + ": " + subject
        
        p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
        p.communicate(msg.as_bytes())
    
    if not hasFlag("m"):
        os.system("run_keybase > /dev/null 2>&1")
        os.system(f"keybase chat send pearwasps_io \"{host}: {subject}\" > /dev/null 2>&1")

# send("TestingFunciton", "This is a test of an automated messaging script")
