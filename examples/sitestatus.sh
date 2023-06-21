Source: Github Gist https://gist.github.com/davetromp/4165179

#!/bin/bash

################################################################################

# This script will check to see if a website is up/down by pinging the url
# If there is no response an email wil be send via an external smtp mail server
# If the site status is down an email will be send when the site is up again

# set your check interval here :-) #############################################
interval=3600 # hour

# begin status ; DO NOT CHANGE #################################################
stat=0 # this is the status UP; status 1 is DOWN

# your url #####################################################################
url="localhost"

# email settings ###############################################################

send(){ # subject message
	toemail="you@gmail.com"
	fromemail="you@gmail.com"
	smtpserver="smtp.gmail.com"
	port=587
	username="you@gmail.com"
	passw="YourVerySecretPassword"
	sendemail -f "$fromemail" -t "$toemail" -u "$1" -m "$2" -s \
	"$smtpserver:$port" -xu "$username" -xp "$passw" -o tls=yes -q
}

# check url ####################################################################

while :
do
	wget --server-response --spider $url # checking the actual response is
        # better, because server me be running and returning pings while our
        # site could be down. This wget will only return exit 0 if response is
        # 200 ok
        #ping -c 1 $url | grep "0%" > /dev/null
	# if we get zero percent lost in the ping, all is well and we should get
	# exit status 0 on this last program run / exited
	if [ "$?" -eq 0 ] # so if we have exit status of zero then server is UP
	then
		# only if the current status is DOWN (1) then we want to notify
		# the new status up and change the stat variable accordingly
		if [ "$stat" -eq 1 ]
		then
		echo "UP | `date`" >> "$url-status.log"
		send "$url is UP" "UP | `date`"
		stat=0
		fi
	else
		# same as above but the other way around
		if [ "$stat" -eq 0 ]
		then
		echo "DOWN | `date`" >> `echo "$url-status.log"`
      		send "$url is DOWN" "DOWN | `date`"
		stat=1
		fi
	fi

	sleep $interval

done

exit

# Ciao #########################################################################