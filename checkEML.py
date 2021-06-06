#!/usr/bin/env python3
# Source: https://gist.github.com/jasonrdsouza/1674794

import email, getpass, imaplib, os, mailbox
import yaml, re
from utils import cPrint


def fetchMail(box):
    try:
        status, temp = con.select(box, readonly=True)
        if "OK" not in status:
            return

        # you could filter using the IMAP rules here (check http://www.example-code.com/csharp/imap-search-critera.asp)
        status, items = con.search(None, "ALL")
    except:
        return

    items = items[0].split()  # getting the mails id
    cPrint(f"Reading {box}: {len(items)} total emails")
    pullUUID = re.compile(r'.*? \(X-GM-MSGID (?P<UUID>.*)\)')

    for emailid in items:
        status, UUID = con.fetch(emailid, "X-GM-MSGID")
        if "OK" not in status:
            continue
        UUID = UUID[0].decode()
        UUID = pullUUID.match(UUID).group('UUID')

        if UUID in cache:
            continue

        # fetching the mail, '`(RFC822)`' means 'get the whole stuff', but you can ask for headers only, etc
        status, data = con.fetch(emailid, "(RFC822)")
        body = data[0][1]
        mail = email.message_from_bytes(body)
        cache.append(UUID)
        mail["X-GM-MSGID"] = UUID
        mbox.add(mail)

        # parsing the mail content to get a mail object
        # mail = email.message_from_string(body)
        # print(mail)

        # Check if any attachments at all
        if mail.get_content_maintype() != "multipart":
            continue

        # we use walk to create a generator so we can iterate on the parts and forget about the recursive headach
        for part in mail.walk():
            # multipart are just containers, so we skip them
            if part.get_content_maintype() == "multipart":
                continue

            # is this part an attachment ?
            if part.get("Content-Disposition") is None:
                continue

            try:
                filename = part.get_filename()
                
                dirpath = os.path.join(aPath, UUID)
                filepath = os.path.join(aPath, UUID, filename)
            except:
                continue

            # Check if its already there
            if not os.path.exists(dirpath):
                os.mkdir(dirpath)            
            if not os.path.isfile(filepath):
                # finally write the stuff
                fp = open(filepath, "wb")
                fp.write(part.get_payload(decode=True))
                fp.close()


conf = yaml.safe_load(open("data/gmail.yml"))

# mbox = mailbox.mbox('data/gmail.mbox')
mbox = mailbox.Maildir(conf["maildir"])
mbox.lock()

aPath = conf["maildir"] + "/attr"
aPath = os.path.join(os.getcwd(), aPath)
aPath = os.path.abspath(aPath)
if not os.path.exists(aPath):
    os.mkdir(aPath)

cPath = conf["maildir"] + "/cache"
cPath = os.path.join(os.getcwd(), cPath)
cPath = os.path.abspath(cPath)
if not os.path.exists(cPath):
    open(cPath, "a").close()

cache = []
with open(cPath, "r") as f:
    for UUID in f:
        # remove linebreak which is the last character of the string
        cache.append(UUID[:-1])


# connecting to the gmail imap server
con = imaplib.IMAP4_SSL(conf["server"])
con.login(conf["username"], conf["password"])


boxReg = re.compile(r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" (?P<name>.*)')

status, boxes = con.list()
for box in boxes:
    box = box.decode()
    flags, delimiter, name = boxReg.match(box).groups()
    name = name.strip('"')
    fetchMail(name)
# exit(0)
mbox.unlock()

with open(cPath, "w") as f:
    for UUID in cache:
        f.write(f"{UUID}\n")
