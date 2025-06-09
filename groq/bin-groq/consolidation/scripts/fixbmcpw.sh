#! /bin/bash

FN=$1_bmc_ips.csv
echo "Parsing: ${FN}"
while IFS="," read -r IP USER PW
do
    COMMAND="ipmitool -H $IP -U root -P "GroqRocks1" user test 3 20 GroqRocks1"
    echo Checking: $IP
    RESULT=$(eval " ${COMMAND}")
    if [[ "$RESULT" != *"Success"* ]]
    then
        echo $IP Failed: Trying to reset username/password:
        ipmitool -H $IP -U ADMIN -P $PW user set name 3 "root"
        ipmitool -H $IP -U ADMIN -P $PW user enable 3
        ipmitool -H $IP -U ADMIN -P $PW user priv 3 0x4 1
        ipmitool -H $IP -U ADMIN -P $PW user set password 3 "GroqRocks1"
    fi
done < $FN
