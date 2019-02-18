#!/bin/bash

export config=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()); print y")
if [[ "${config}" != "None" ]]; then
export influx_host=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print y.get('host')")
export influx_port=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print y.get('port',8086)")
export jmeter_db=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print y.get('jmeter_db', 'jmeter')")
export comparison_db=$(python -c "import yaml; y = yaml.load(open('/tmp/config.yaml').read()).get('influx',{}); print y.get('comparison_db', 'comparison')")
export report_portal=$(python -c "import yaml; print yaml.load(open('/tmp/config.yaml').read()).get('reportportal',{})")
export jira=$(python -c "import yaml; print yaml.load(open('/tmp/config.yaml').read()).get('jira',{})")
else
export influx_host="None"
export jira="{}"
export report_portal="{}"
fi

args=$@

if [[ "${influx_host}" != "None" ]]; then
echo "influx.host=${influx_host}" >> /mnt/jmeter/test_info.txt
echo "influx.port=${influx_port}" >> /mnt/jmeter/test_info.txt
echo "influx.db=${jmeter_db}" >> /mnt/jmeter/test_info.txt
echo "comparison_db=${comparison_db}" >> /mnt/jmeter/test_info.txt
if [[ ${args} != *"-Jinflux.host"* ]]; then
args="${args} -Jinflux.host=${influx_host}"
fi
if [[ ${args} != *"-Jinflux.port"* ]]; then
args="${args} -Jinflux.port=${influx_port}"
fi
if [[ ${args} != *"-Jinflux.db"* ]]; then
args="${args} -Jinflux.db=${jmeter_db}"
fi
fi
set -e
export JVM_ARGS="-Xmn1g -Xms1g -Xmx1g"

python ./place_listeners.py ${args// /%} ./backend_listener.jmx

echo "START Running Jmeter on `date`"
echo "JVM_ARGS=${JVM_ARGS}"
echo "jmeter args=${args}"
echo "start_time=$(date +%s)000" >> /mnt/jmeter/test_info.txt
jmeter ${args}
echo "end_time=$(date +%s)000" >> /mnt/jmeter/test_info.txt

python ./remove_listeners.py ${args// /%}
echo "Tests are done"
echo "Generating metrics for comparison table ..."
python ./compare_build_metrix.py ${args// /%}
if [[ "${report_portal}" != "{}" || "${jira}" != "{}" ]]; then
echo "Parsing errors ..."
python ./error_parser.py ${args// /%}
echo "END Running Jmeter on `date`"
fi
rm -f /mnt/jmeter/test_info.txt