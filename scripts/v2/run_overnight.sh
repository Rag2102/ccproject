#!/bin/zsh
# Weeks 18, 19, 20 and the Week 21 seed replication in sequence (about 12.5 hours on 8 cores). Each stage is resumable: if the Mac
# sleeps or a stage stops, run this again and finished work is skipped.
cd ~/Desktop/ccproject
mkdir -p logs/w18
scripts/v2/run_w18.sh > logs/w18/driver.log 2>&1
mkdir -p logs/w19 && scripts/v2/run_w19.sh > logs/w19/driver.log 2>&1
mkdir -p logs/w20 && scripts/v2/run_w20.sh > logs/w20/driver.log 2>&1
mkdir -p logs/w21 && scripts/v2/run_w21.sh > logs/w21/driver.log 2>&1
echo "all done $(date)" > logs/overnight_done.txt
