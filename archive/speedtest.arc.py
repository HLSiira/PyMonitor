import os
import re
import time
import csv
import random
import statistics
import subprocess
from collections import namedtuple

daily_test = subprocess.Popen('/usr/local/bin/speedtest-cli --simple', shell=True, stdout=subprocess.PIPE).stdout.read().decode('utf-8')

# daily_test = (
#    f"Ping: {round(random.uniform(20,60), 3)} ms"
#    f"Download: {round(random.uniform(60,95), 2)} Mbit/s"
#    f"Upload: {round(random.uniform(5,10), 2)} Mbit/s "
# )

ping = re.findall('Ping:\s(.*?)\s', daily_test, re.MULTILINE)
download = re.findall('Download:\s(.*?)\s', daily_test, re.MULTILINE)
upload = re.findall('Upload:\s(.*?)\s', daily_test, re.MULTILINE)

ping = ping[0].replace(',', '.')
download = download[0].replace(',', '.')
upload = upload[0].replace(',', '.')
date_time = time.strftime('%m/%d/%y %H:%M')
#date_time = f"{date_time:>14}"

header = ['Date  Time', 'Ping(ms)', 'Down(Mb/s)', 'Up(Mb/s)']
#response = f"{date_time},{ping[0]},{download[0]},{upload[0]}"

daily_test = [date_time, ping, download, upload]

# print('{:^14}|{:>10}|{:>12}|{:>10}'.format(*header))
# print('{:>14}|{:>10}|{:>12}|{:>10}'.format(*daily_test))

SpeedTest = namedtuple('SpeedTest', ('date_time ping download upload'))
daily_test = SpeedTest(*daily_test)


csv_tests_daily = f'/home/pi/tools/speedtest/daily_tests/speedtest_daily_{time.strftime("%m-%d")}.csv'
csv_tests_yearly = f'/home/pi/tools/speedtest/speedtest_yearly_{time.strftime("%y")}.csv'

history_daily, history_yearly = [], []

history_daily.append(daily_test)

try:
    if os.stat(csv_tests_daily).st_size != 0:
        with open(csv_tests_daily) as csvfile:
            readCSV = csv.reader(csvfile, delimiter='|')

            next(readCSV)

            for row in readCSV:
                history_daily.append(SpeedTest(*row))
except:
    pass

with open(csv_tests_daily, 'w') as csvfile:
    writer = csv.writer(csvfile)
    header = '{:^14}|{:>10}|{:>12}|{:>10}'.format(*header).split('|', 0)
    writer.writerow(header)

    for speedtest in history_daily:
        speedtest = '{:^14}|{:>10}|{:>12}|{:>10}'.format(*speedtest).split('|', 0)
        writer.writerow(speedtest)

if int(time.strftime('%H')) >= 23:

    Summary = namedtuple('Summary', ('date average_ping lowest_download average_download highest_download lowest_upload average_upload highest_upload'))

    daily_summary = Summary(time.strftime('%m-%d'),
           round(statistics.mean([float(test.ping) for test in history_daily]), 2), round(min([float(test.download) for test in history_daily]), 2),
                            round(statistics.mean(
                                [float(test.download) for test in history_daily]), 2),
                            round(max([float(test.download)
                                       for test in history_daily]), 2),
                            round(min([float(test.upload)
                                       for test in history_daily]), 2),
                            round(statistics.mean(
                                [float(test.upload) for test in history_daily]), 2),
                            round(max([float(test.upload)
                                       for test in history_daily]), 2)
                            )
    daily_summary
    daily_summary = [daily_summary.date,
                     daily_summary.average_ping,
                     f'{daily_summary.lowest_download}/{daily_summary.average_download}/{daily_summary.highest_download}',
                     f'{daily_summary.lowest_upload}/{daily_summary.average_upload}/{daily_summary.highest_upload}'
                     ]
    print("Speedtest: ", daily_summary)

    history_yearly.append(daily_summary)

    try:
        if os.stat(csv_tests_yearly).st_size >= 0:
            with open(csv_tests_yearly) as csvfile:
                readCSV = csv.reader(csvfile, delimiter='|')

                next(readCSV)
                for row in readCSV:
                    history_yearly.append(row)
    except:
        pass

    with open(csv_tests_yearly, 'w') as csvfile:

        writer = csv.writer(csvfile)

        header = [
            'Date', 'Avg Ping(ms)', 'Download Speeds(Mb/s)', 'Upload Speeds(Mb/s)']
        header = '{:^7}|{:>12}|{:>22}|{:>20}'.format(*header)

        writer.writerow(header.split('|', 0))

        for speedtest in history_yearly:
            speedtest = '{:^7}|{:^12}|{:^22}|{:^20}'.format(*speedtest)
            writer.writerow(speedtest.split('|', 0))

if float(daily_test.download) < 60 or float(daily_test.upload) < 5:
    from email.mime.text import MIMEText
    from subprocess import Popen, PIPE

    msg = f"Glenora Internet speeds are low: D({daily_test.download})/U({daily_test.upload})\n"
    msg = msg + f"TimeStamp: {daily_test.date_time}"
    msg = MIMEText(msg)

    msg["From"] = "Catalog879 <Catalog879@gmail.com>"
    msg["To"] = "Liam Siira <Liam@siira.us>"
    msg["Subject"] = "Internet Speed Alert: Glenora"
    p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
    p.communicate(msg.as_bytes())
