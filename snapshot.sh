#!/bin/bash
echo "Artemis autobackup started" 
 
## Directory containing the script / local destination of the backups
desdir='/home/liam/HTML'
tardir='/var/www/html'

month=$(date +%^b)
week=W$((($(date +%-d)-1)/7+1))
host=ARTEMIS
echo -e "\tSaving as "$host-$month-$week".tar.gz"
 
# Zip the target directory into a compressed file in the backup directory
tar --exclude-vcs -zcf $desdir/$host-$month-$week.tar.gz -C $tardir .

# Wait to ensure zip is complete
sleep 2s
echo -e "\tHTML Files successfully compressed"


## Directory containing the script / local destination of the backups
tardir='/var/www/html/atheos/workspace/pMonitor/data/speedtest/'
host=Speedtest
 
# DO NOT DELETE ARCHIVE FOLDER
echo -e "\tDeleting archives older than 3 months"
days=$(( ( $(date '+%s') - $(date -d '3 months ago' '+%s') ) / 86400 ))
# find $desdir/*.tar.gz -mtime +$days -type f -delete
find $tardir/daily/* -mtime +90 -type f -delete


echo -e "\tRCloning to Google Drive"
# rclone copy $tardir drive-liam-siira:BACKUP/SPEED
rclone sync $desdir drive-liam-siira:BACKUP/ARTEMIS
echo -e "\tRCloning from Google Drive"


rclone sync drive-liam-siira:Music /mnt/md0/liam/files/Media/RunningMusic
rclone sync drive-liam-siira:BACKUP /mnt/md0/liam/files/Archive/BACKUP
rclone sync drive-liam-siira:USAF /mnt/md0/liam/files/USAF

rclone sync drive-liam-siira:Dogs /mnt/md0/liam/files/GDrive/Dogs
rclone sync drive-liam-siira:Recovery /mnt/md0/liam/files/GDrive/Recovery

echo -e "\tRClone finished"