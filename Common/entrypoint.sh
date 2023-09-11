#!/bin/bash
set -eu

function set_jvm_memory() {
  freeMem=`awk '/MemFree/ { print int($2/1024) }' /proc/meminfo`
  s=$(($freeMem/10*8))
  x=$(($freeMem/10*8))
  n=$(($freeMem/10*2))
  export HEAP="-Xmn${n}m -Xms${s}m -Xmx${x}m"
  echo "HEAP=${HEAP}"
}

function run_master() {
  while true; do
    sleep 5
    echo "jmeter master running ..."
  done
}

function run_slave() {
  echo "start jmeter slave."
  set_jvm_memory
  echo ${JMETER_BIN}
  ls -la ${JMETER_BIN}
  ${JMETER_BIN}/jmeter-server -Jserver.rmi.ssl.disable=true

}

output_dir="/tests/output"

function run_test() {
  echo "run jmeter test."
  local remotes="$1"
  local jmx_file="$2"
  jmeter -n -R ${remotes} -t ${jmx_file} -j ${output_dir}/master.log -l ${output_dir}/result.jtl -e -o ${output_dir}/reports
}

function run_test_with_exit() {
  echo "run jmeter test with client exit."
  local remotes="$1"
  local jmx_file="$2"
  ls -la /opt/apache-jmeter-5.1.1/bin
  ${JMETER_BIN}/jmeter -n -R ${remotes} -t ${jmx_file} -j ${output_dir}/master.log -l ${output_dir}/result.jtl -e -o ${output_dir}/reports -X
}

if [[ $1 == "master" ]]; then
  run_masterpe

fi

if [[ $1 == "slave" ]]; then
  run_slave
fi

if [[ $1 == "test" ]]; then
  remotes="$2"
  jmx_file="$3"
  echo "remote"
  echo ${remotes}
  echo "jmx"
  echo ${jmx_file}
  run_test_with_exit ${remotes} ${jmx_file}
fi

echo "$(date): jmeter entrypoint done."