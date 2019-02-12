#!/bin/bash

set -e
freeMem=`awk '/MemFree/ { print int($2/1024) }' /proc/meminfo`
s=1
x=1
n=1
export JVM_ARGS="-Xmn${n}g -Xms${s}g -Xmx${x}g"

args=$@
python ./place_listeners.py ${args// /%} ./backend_listener.jmx

echo "START Running Jmeter on `date`"
echo "JVM_ARGS=${JVM_ARGS}"
echo "jmeter args=$@"
echo "build.id=floodIO_${JOB_NAME}_${BUILD_ID}" >> /mnt/jmeter/test_info.txt
echo "start_time=$(date +%s)000" >> /mnt/jmeter/test_info.txt
jmeter $@
echo "end_time=$(date +%s)000" >> /mnt/jmeter/test_info.txt

python ./remove_listeners.py ${args// /%}
echo "Tests are done"
echo "Generating metrics for comparison table ..."
python ./compare_build_metrix.py ${args// /%}
echo "Parsing errors ..."
python ./error_parser.py ${args// /%}
echo "END Running Jmeter on `date`"
