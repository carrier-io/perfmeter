#!/bin/bash

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
          if [[ $param =~ test.type=(.+) ]]; then
            export test_type=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ test_name=(.+) ]]; then
            export test_name=${BASH_REMATCH[1]}
          fi
          if [[ $param =~ VUSERS=(.+) ]]; then
            export users=${BASH_REMATCH[1]}
          fi
done < "$property_file"
fi

export config=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()); print(y)")
if [[ "${config}" != "None" ]]; then
echo "Extracting InfluxDB configuration from config.yaml"
export influx_host=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('host'))")
export influx_port=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('port', ''))")
export jmeter_db=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('jmeter_db', ''))")
export comparison_db=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print(y.get('comparison_db', ''))")
export report_portal=$(python -c "import yaml; print(yaml.load(open('/tmp/config.yaml').read()).get('reportportal',{}))")
export jira=$(python -c "import yaml; print(yaml.load(open('/tmp/config.yaml').read()).get('jira',{}))")
export loki=$(python -c "import yaml; print(yaml.load(open('/tmp/config.yaml').read()).get('loki',{}))")
else
export jira="{}"
export report_portal="{}"
export loki="{}"
fi

arr=(${args// / })

if [[ ${args} == *"-Jtest.type="* ]]; then
for i in "${arr[@]}"; do
          if [[ $i =~ -Jtest.type=(.+) ]]; then
            export test_type=${BASH_REMATCH[1]}
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
          fi
          if [[ $i =~ -Jusers=(.+) ]]; then
            export users=${BASH_REMATCH[1]}
          fi
          if [[ $i =~ -JVUSERS=(.+) ]]; then
            export users=${BASH_REMATCH[1]}
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

if [[ -z "${test_name}" ]]; then
export test_name="test"
fi

if [[ -z "${test_type}" ]]; then
export test_type="test"
fi

sudo sed -i "s/LOAD_GENERATOR_NAME/${lg_name}_${lg_id}/g" /etc/telegraf/telegraf.conf
sudo sed -i "s/INFLUX_HOST/http:\/\/${influx_host}:${influx_port}/g" /etc/telegraf/telegraf.conf
sudo service telegraf restart
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
set -e

if [[ -z "${JVM_ARGS}" ]]; then
  export JVM_ARGS="-Xmn1g -Xms1g -Xmx1g"
fi
echo "Using ${JVM_ARGS} as JVM Args"

python ./place_listeners.py ${args// /%} ./backend_listener.jmx

echo "START Running Jmeter on `date`"
echo "JVM_ARGS=${JVM_ARGS}"
echo "jmeter args=${args}"
start_time=$(date +%s)000
cd "jmeter/apache-jmeter-5.0/bin/"
"$DEFAULT_EXECUTION" "$JOLOKIA_AGENT" $JVM_ARGS -jar "/jmeter/apache-jmeter-5.0//bin/ApacheJMeter.jar" ${args}
cd "/"
end_time=$(date +%s)000

python ./remove_listeners.py ${args// /%}

if [[ -z "${build_id}" ]]; then
export _build_id=""
else
export _build_id="-b ${build_id}"
fi

echo "Tests are done"
echo "Generating metrics for comparison table ..."
python ./compare_build_metrix.py -t $test_type -l ${lg_id} ${_build_id} -s $test_name -u $users -st ${start_time} -et ${end_time} -i ${influx_host} -p ${influx_port} -cdb ${comparison_db} -f "/jmeter/apache-jmeter-5.0/bin/simulation.log"
if [[ "${report_portal}" != "{}" || "${jira}" != "{}" || "${loki}" != "{}" ]]; then
echo "Parsing errors ..."
python ./logparser.py -t $test_type -s $test_name -st ${start_time} -et ${end_time} -i ${influx_host} -p ${influx_port} -f "/jmeter/apache-jmeter-5.0/bin/simulation.log"
echo "END Running Jmeter on `date`"
fi