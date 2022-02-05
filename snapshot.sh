#!/bin/bash

HOST="HTML"
echo "$HOST autobackup started" 

BACKUP="/home/liam/Artemis/$HOST"
TARGET="/var/www/html"
AGEOFF="90"

read YY MMM DD <<<$(date +"%y %^b %d")

WK="W$((($DD-1)/7+1))"

echo -e "\tCompressing and saving as $HOST-$MMM-$WK.tar.gz"
tar --exclude-vcs -zcf $BACKUP/$HOST-$MMM-$WK.tar.gz -C $TARGET .

echo -e "\tDeleting older TARs and snapshots"
find $BACKUP -type f -mtime +$AGEOFF -delete

##################################

HOST=Speedtest
TARGET="/home/liam/Artemis/SpeedTest"

echo "$HOST autobackup started" 

# DO NOT DELETE ARCHIVE FOLDER
echo -e "\tDeleting archives older than 3 months"
days=$(( ( $(date '+%s') - $(date -d '3 months ago' '+%s') ) / 86400 ))
# find $desdir/*.tar.gz -mtime +$days -type f -delete
find $TARGET/daily/* -mtime +90 -type f -delete


echo -e "\tRCloning to Google Drive"
TARGET="/home/liam/Artemis"
rclone sync $TARGET liam-siira-drive:Archive/Artemis
echo -e "\tRClone finished"