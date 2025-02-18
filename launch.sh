#!/bin/bash

#RUN INFLUXDB
bash entrypoint.sh influxd &

args=$@
if [[ ${args} == *"-q "* ]]; then
IFS=" " read -ra PARAMS <<< "$args"
for index in "${!PARAMS[@]}"
do
    if [[ ${PARAMS[index]} == "-q" ]]; then
        property_file=${PARAMS[index + 1]}
    fi
done
fi

if [[ "${property_file}" ]]; then
echo "Extracting InfluxDB configuration from property file - $property_file"
while IFS= read -r param
do
          if [[ $param =~ influx.host=(.+) ]]; then
            export influx_host=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ influx.port=(.+) ]]; then
            export influx_port=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ influx.db=(.+) ]]; then
            export jmeter_db=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ comparison_db=(.+) ]]; then
            export comparison_db=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ test_type=(.+) ]]; then
            export test_type=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ test_name=(.+) ]]; then
            export test_name=${BASH_REMATCH[1]}
          fi

done < "$property_file"
fi

if [[ -z "${config_yaml}" ]]; then
export config=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()); print(y)")
else
$(python -c "import json; import os; f = open('/tmp/config.yaml', 'w'); f.write(json.loads(os.environ['config_yaml']))")
export config=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()); print(y)")
fi
if [[ "${config}" != "None" ]]; then
echo "Extracting InfluxDB configuration from config.yaml"
export influx_host=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('host'))")
export influx_port=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('port', ''))")
export influx_user=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('user',''))")
export influx_password=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('password',''))")
export jmeter_db=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('influx_db', 'jmeter'))")
export comparison_db=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('comparison_db', ''))")
if [[ -z "${loki_host}" ]]; then
export loki_host=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('loki',{}); print(y.get('host',''))")
fi
if [[ -z "${loki_port}" ]]; then
export loki_port=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('loki',{}); print(y.get('port', '3100'))")
fi
fi

arr=(${args// / })

if [[ ${args} == *"-Jtest_type="* ]]; then
for i in "${arr[@]}"; do
          if [[ $i =~ -Jtest_type=(.+) ]]; then
            export test_type=${BASH_REMATCH[1]}
          fi
    done
fi

if [[ ${args} == *"-Jenv_type="* ]]; then
for i in "${arr[@]}"; do
          if [[ $i =~ -Jenv_type=(.+) ]]; then
            export env=${BASH_REMATCH[1]}
          fi
    done
fi


if [[ ${args} == *"-Jtest_name="* ]]; then
for i in "${arr[@]}"; do
          if [[ $i =~ -Jtest_name=(.+) ]]; then
            export test_name=${BASH_REMATCH[1]}
          fi
    done
fi

for i in "${arr[@]}"; do
          if [[ $i =~ -Jbuild.id=(.+) ]]; then
            export build_id=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jlg.id=(.+) ]]; then
            export lg_id=${BASH_REMATCH[1]}
          else
            export lg_id="Lg_"$RANDOM"_"$RANDOM
          fi
    done

if [[ ${args} == *"-Jinflux.host"* || ${args} == *"-Jinflux.port"* || ${args} == *"-Jjmeter_db"* || ${args} == *"-Jcomparison_db"* ]]; then
arr=(${args// / })
for i in "${arr[@]}"; do
          if [[ $i =~ -Jinflux.host=(.+) ]]; then
            influx_host=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jinflux.port=(.+) ]]; then
            influx_port=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jinflux.db=(.+) ]]; then
            jmeter_db=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jcomparison_db=(.+) ]]; then
            comparison_db=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jtelegraf_db=(.+) ]]; then
            telegraf_db=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jinflux.username=(.+) ]]; then
            influx_user=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -Jinflux.password=(.+) ]]; then
            influx_password=${BASH_REMATCH[1]}
          fi
      done
fi

if [[ -z "${influx_port}" ]]; then
influx_port=8086
fi

if [[ -z "${jmeter_db}" ]]; then
jmeter_db="jmeter"
fi

if [[ -z "${comparison_db}" ]]; then
comparison_db="comparison"
fi

if [[ -z "${telegraf_db}" ]]; then
telegraf_db="telegraf"
fi

if [[ -z "${test_name}" ]]; then
export test_name="test"
fi

if [[ -z "${test_type}" ]]; then
export test_type="demo"
fi

if [[ -z "${env}" ]]; then
export env="demo"
fi

if [[ -z "${build_id}" ]]; then
export build_id=${test_name}"_"${test_type}"_"$RANDOM
fi

if [[ "${loki_host}" ]]; then
/usr/bin/promtail/promtail-linux-amd64 --client.url=${loki_host}:${loki_port}/api/prom/push --client.external-labels=hostname=${lg_id},project=${project_id},report_id=${report_id},build_id=${build_id} -config.file=/etc/promtail/promtail-logger.yaml &
fi

if [[ "${influx_host}" ]]; then
sudo sed -i "s/BUILD_ID/${build_id}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/LOAD_GENERATOR_NAME/${lg_name}_${test_name}_${lg_id}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/INFLUX_HOST/http:\/\/${influx_host}:${influx_port}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/INFLUX_USER/${influx_user}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/INFLUX_PASSWORD/${influx_password}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/telegraf/${telegraf_db}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/TEST_NAME/${test_name}/g" /etc/telegraf/telegraf_local_results.conf
sudo service telegraf restart
sudo telegraf -config /etc/telegraf/telegraf_local_results.conf &
fi
DEFAULT_EXECUTION="/usr/bin/java"
JOLOKIA_AGENT="-javaagent:/opt/java/jolokia-jvm-1.6.0-agent.jar=config=/opt/jolokia.conf"

if [[ "${influx_host}" ]]; then
if [[ ${args} != *"-Jinflux.host"* ]]; then
args="${args} -Jinflux.host=${influx_host}"
fi
if [[ ${args} != *"-Jinflux.port"* ]]; then
args="${args} -Jinflux.port=${influx_port}"
fi
if [[ ${args} != *"-Jinflux.db"* ]]; then
args="${args} -Jinflux.db=${jmeter_db}"
fi
if [[ ${args} != *"-Jcomparison_db"* ]]; then
args="${args} -Jcomparison_db=${comparison_db}"
fi
fi
if [[ ${args} != *"-Jlg.id"* ]]; then
args="${args} -Jlg.id=${lg_id}"
fi
if [[ ${args} != *"-Jbuild.id"* ]]; then
args="${args} -Jbuild.id=${build_id}"
fi
if [[ -z "${influx_user}" ]]; then
export _influx_user=""
else
export _influx_user="-iu ${influx_user}"
fi

if [[ -z "${influx_password}" ]]; then
export _influx_password=""
else
export _influx_password="-ip ${influx_password}"
fi

if [[ "${influx_host}" ]]; then
export _influx_host="-i ${influx_host}"
else
export _influx_host=""
fi
args="${args} -j /tmp/jmeter_logs.log"
set -e

if [[ -z "${JVM_ARGS}" ]]; then
  export JVM_ARGS="-Xms3g -Xmx3g"
fi
echo "Using ${JVM_ARGS} as JVM Args"
export tests_path=/mnt/jmeter
python minio_tests_reader.py
python minio_additional_files_reader.py
mkdir '/tmp/data_for_post_processing'
#python minio_poster.py -t $test_type -s $test_name -b ${build_id} -l ${lg_id} ${_influx_host} -p ${influx_port} -idb ${jmeter_db} -icdb ${comparison_db} -en ${env} ${_influx_user} ${_influx_password}
python downsampling.py -t $test_type -s $test_name -b ${build_id} -l ${lg_id} ${_influx_host} -p ${influx_port} -idb ${jmeter_db} -en ${env} ${_influx_user} ${_influx_password} &

if [[ "${influx_host}" ]]; then
python ./place_listeners.py ${args// /%} ./backend_listener.jmx
fi

echo "START Running Jmeter on `date`"
echo "jmeter args=${args}"
cd "jmeter/apache-jmeter-${JMETER_VERSION}/bin/"
echo "$DEFAULT_EXECUTION" "$JOLOKIA_AGENT" $JVM_ARGS -jar "/jmeter/apache-jmeter-${JMETER_VERSION}//bin/ApacheJMeter.jar" $custom_cmd ${args}
"$DEFAULT_EXECUTION" "$JOLOKIA_AGENT" $JVM_ARGS -jar "/jmeter/apache-jmeter-${JMETER_VERSION}//bin/ApacheJMeter.jar" $custom_cmd ${args}
cd "/"
if [[ "${influx_host}" ]]; then
python ./remove_listeners.py ${args// /%}
fi

echo "Tests are done"

python post_processor.py -t $test_type -s $test_name -b ${build_id} -l ${lg_id} ${_influx_host} -p ${influx_port} -idb ${jmeter_db} -icdb ${comparison_db} -en ${env} ${_influx_user} ${_influx_password}
echo "Results processing. Sleep for 1 minute"
sleep 60
echo "END Running Jmeter on `date`"