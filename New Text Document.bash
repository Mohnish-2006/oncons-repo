#!/bin/bash

for i in {1..60}; do
 d=$(date -j -v-"$i"d +"%Y-%m-%d") # Subtract $i days from current date
 h=$(( RANDOM % (23 + 1) ))
 m=$(( RANDOM % (59 + 1) ))
 echo "$d $h:$m"
 git add . > /dev/null # Suppress output
 GIT_COMMITTER_DATE="$d $h:$m"; GIT_AUTHOR_DATE="$d $h:$m";
 git commit -m "Auto Commit $(($i+100)) at $d $h:$((10#$((RANDOM%9))))";
done