#!/bin/bash
#Script to report public IP address change
#By: Ronny L. Bull
TO="email@address.com"
FROM="alerts@address.com"
#The file that contains the current pubic IP
EXT_IP_FILE="/path/to/ipaddressfile"
#Get the current public IP from whatsmyip.com
CURRENT_IP=$(curl http://ifconfig.me/ip)
#Check file for previous IP address
if [ -f $EXT_IP_FILE ]; then
KNOWN_IP=$(cat $EXT_IP_FILE)
else
KNOWN_IP=
fi
#See if the IP has changed
if [ "$CURRENT_IP" != "$KNOWN_IP" ]; then
echo $CURRENT_IP > $EXT_IP_FILE
#If so send an alert
echo "Subject: The IP Address at home has changed
The IP address at home has been changed to $CURRENT_IP" | mail -s ${FROM} ${TO}
logger -t ipcheck -- IP changed to $CURRENT_IP
else
#If not just report that it stayed the same
echo "Subject: The IP Address at home is the same
The IP address at home stayed the same $CURRENT_IP" | sendmail -f ${FROM} ${TO}
logger -t ipcheck -- NO IP change
fi