#!/bin/bash
while true
do
   # Start the script
   python /Users/ake/Documents/probable_spoon_a/src/avanza_api.py &
   # Get the PID of the process
   PID=$!
   echo $PID

   # Countdown for 15 minutes (900 seconds)
   for ((i=900; i>0; i--)); do
      sleep 1
      # Check if the remaining time is a multiple of 30
      if (( i % 30 == 0 )); then
          # Clear the previous line and print the countdown
          echo -ne "\rScript will restart in $i seconds...      "
      fi
   done

   echo -ne "\rRestarting the script now.           "
   
   # Kill the process
   echo $PID
   kill $PID
   # Wait a moment before restarting
   sleep 5
done
