#!/bin/sh

echo "Restarting Artemis..."

#screen -S spigot -p 0 -X stuff "say &4Server rebooting in 5 minutes^M"
screen -S spigot -p 0 -X stuff 'tellraw @a [{"text":"[Server] ","color":"red"},{"text":"Server restarting in 5 minutes","color":"white"}]^M'

sleep 4m

screen -S spigot -p 0 -X stuff 'tellraw @a [{"text":"[Server] ","color":"red"},{"text":"Server restarting in 1 minute","color":"white"}]^M'

sleep 1m

screen -S spigot -p 0 -X stuff 'tellraw @a [{"text":"[Server] ","color":"red"},{"text":"Server restarting...","color":"white"}]^M'

screen -S spigot -p 0 -X stuff 'stop^M'

sleep 10

date=$(date '%d')

/bin/tar -czf /home/liam/storage/spigot/spigot_1.14_$date.tar.gz /home/liam/spigot_1.14

sleep 5

#sudo /sbin/reboot
/home/liam/spigot_1.14/start_spigot.sh
#ps auxw | grep spigot | grep -v grep > /dev/null

#if [ $? != 0 ]
#then
#    /etc/init.d/apache2 start > /dev/null
#fi
