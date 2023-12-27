#!/bin/bash

#=============================================================================80
# Configuration Settings
#=============================================================================80
HOST="Artemis"
USER_KEY=""
API_TOKEN=""
AGEOFF="90"
BACKUP_DIR=""
WEEKNUM=$(date +"%V")

#=============================================================================80
# Function to send Pushover notification
#=============================================================================80
sendNotification() {
    local message=$1
    curl -s \
      --form-string "token=$API_TOKEN" \
      --form-string "user=$USER_KEY" \
      --form-string "title=$HOST: Backup Alert" \
      --form-string "message=$MESSAGE" \
      --form-string "priority=1" \
      --form-string "ttl=43200" \
      https://api.pushover.net/1/messages.json >/dev/null 2>&1
}

#=============================================================================80
# HTML Backup
#=============================================================================80
NAME="HTML"
echo -e "$NAME backup started" 
BACKUP="/home/liam/Artemis/$NAME"
TARGET="/var/www/html"
mkdir -p "$BACKUP" || { sendNotification "Cannot create directory for $NAME"; return 1; }

ARCHIVE="$NAME-W$WEEKNUM.tar.gz"
echo -e "Compressing and saving as $ARCHIVE"
tar --exclude-vcs -zcf "$BACKUP/$ARCHIVE" -C "$TARGET" . || { sendNotification "TAR command failed on $NAME"; return 1; }

echo -e "Deleting older TARs and snapshots of $TARGET"
find "$BACKUP" -type f -mtime +"$AGEOFF" -delete || { sendNotification "Cleanup failed on $NAME"; return 1; }

#=============================================================================80
# Speedtest Backup
#=============================================================================80
NAME=Speedtest
echo -e "$NAME backup started" 
TARGET="/home/liam/Artemis/SpeedTest"

echo -e "Deleting archives older than 3 months"
find "$TARGET/daily" -type f -mtime +"$AGEOFF" -delete || { sendNotification "Cleanup failed on $NAME"; return 1; }

#=============================================================================80
# rClone to Google Drive
#=============================================================================80
echo -e "RCloning to Google Drive"
RCLONE_TARGET="drive-liam-siira:Backup/Servers/$HOST"
rclone sync "/home/liam/$HOST" "$RCLONE_TARGET" || { sendNotification "RClone sync failed"; exit 1; }
echo -e "Daily Backup and RClone finished"
