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

jmeter $@

python ./remove_listeners.py ${args// /%}
echo "END Running Jmeter on `date`"
