#!/usr/bin/env python2.7

# source: https://uwot.eu/blog/projects/monitor-hard-disk-smart-status-python/

import subprocess
import re
import socket
import os


hostname = socket.gethostname()
########################################################################
DOMAIN = "domain.tld"
TO = ['receiver']
HDD = ["sdb", "sdc"]
########################################################################
FROM = hostname + "@" + DOMAIN
alert = [0] * len(HDD)

def query_drive_state(drive_id, i):
    p = subprocess.Popen(["smartctl", "-a", "/dev/" + drive_id], stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    
    print(output)

    drive_results = []
    
    # print(output)

    for line in output.splitlines():
        line = str(line)
        if "Reallocated_Sector_Ct" in line:
            value = line.split(" - ", 1)[1]
            if int(value) > 0:
                alert[i] += 1
            drive_results.append("Reallocated sector count*: " + str(int(value)))
        elif "Wear_Leveling_Count" in line:
            # value = re.search(" - (.+?)", line).group(1)
            value = line.split(" - ", 1)[1]
            drive_results.append("Wear leveling count: " + str(int(value)))
        elif "Reallocated_Event_Count" in line:
            value = line.split(" - ", 1)[1]
            
            # try-except is needed in case Rll_Ev_Ct value is messed up
            skip = False
            try:
                value = int(value)
            except Exception:
                skip = True
                drive_results.append("Reallocated event count*: " + 
                                      value)
            if skip is False:
                if value > 0:
                    alert[i] += 1
                    drive_results.append("Reallocated event count*: " + 
                                          str(int(value)))
        elif "Current_Pending_Sector" in line:
            value = line.split(" - ", 1)[1]
            if int(value) > 0:
                alert[i] += 1
            drive_results.append("Current pending sector*: " + 
                                  str(int(value)))
        elif "Offline_Uncorrectable" in line:
            value = line.split(" - ", 1)[1]
            if int(value) > 0:
                alert[i] += 1
            drive_results.append("Offline uncorrectable: " + 
                                  str(int(value)))
        elif "Media_Wearout_Indicator" in line:
            value = line.split(" - ", 1)[1]
            drive_results.append("Media wearout indicator: " + 
                                  str(int(value)))
        '''# DOES NOT WORK WITH PLEXTOR
        elif "Total_LBAs_Written" in line:
            value = re.search(" - (.+?)'", line).group(1)
            drive_results.append("Total LBAs written: " + str((int(value) * 512) * 1.0e-9) + " GB")
            
        elif "Total_LBAs_Read" in line:
            value = re.search(" - (.+?)'", line).group(1)
            drive_results.append("Total LBAs read: " + str((int(value) * 512) * 1.0e-9) + " GB")'''
        
    '''for element in drive_results:
        print(element)'''
    
    print('drive_results', drive_results)
    print('alert', alert)
    return drive_results


def send_alert_sendmail(TEXT, failed_drives):
    if len(failed_drives) == 0:
        SUBJECT = "Subject: " + FROM + " - Failed drives: None"
    else:
        SUBJECT = "Subject: " + FROM + " - Failed drives: " + failed_drives
    message = SUBJECT + "\n\n" + TEXT
    print(message)
    # os.system('echo "' + message + '" | sendmail -v ' + ' '.join(TO))


def main():
    aggregated_results = []
    text = "\n######################################################"
    text += "\n### * Pre-fail attributes, replace the disk if > 0 ###"
    text += "\n######################################################\n"
    
    # Gather HDD health informations
    for i in range(0, len(HDD)):
        aggregated_results.append(query_drive_state(HDD[i], i))

    # Merge HDD health status
    i = 0
    for drive_results in aggregated_results:
        text = text + "\ndev/" + HDD[i] + "\n"
        for element in drive_results:
            text = text + element +"\n"
        i += 1

    # Prepare a list of failing HDD
    failed_drives = ""
    i = 0
    print(alert)
    for element in alert:
        if element >= 1:
            failed_drives += HDD[i]
        i += 1
    
    # Send alert email
    if len(failed_drives) > 0:
        send_alert_sendmail(text, failed_drives)

main()