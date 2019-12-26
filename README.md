# Introduction
*Carrier customized JMeter container*


### Docker tags and versioning

getcarrier/perfmeter:1.0 - Carrier PerfMeter release version 1.0    

getcarrier/perfmeter:latest - bleeding edge, not recommended for production


### Quick start
These simple steps will run jMeter test against your application and generate html and jtl report.

##### 1. Install docker

##### 2. Start container and pass the necessary config options to container:
Example docker invocation:

``` 
docker run --rm -u 0:0 \
       -v <your_local_path_to_tests>:/mnt/jmeter/ \
       -v <your_local_path_to_config/config.yaml>:/tmp/ #optional
       -v <your_local_path_ to_reports>:/tmp/reports \   #optional
       -e "env=<env>" \  #optional, default - 'demo'
       -e "test_type=<test_type>" \  #optional, default - 'demo'
       -e "loki_host={{ http://loki }}" # loki host or IP
       -e "loki_port=3100" # optional, default 3100
       -e "JVM_ARGS='-Xms1g -Xmx2g'"
       getcarrier/perfmeter:1.0 \
       -n -t /mnt/jmeter/<test_name> 
       -q /mnt/jmeter/<properties_file> \    #optional
       -j /tmp/reports/jmeter_$(date +%s).log \   #optional
       -l /tmp/reports/jmeter_$(date +%s).jtl -e \  # optional
       -o /tmp/reports/HtmlReport_$(date +%s)/    #optional
```

`your_local_path_to_reports` - path on your local filesystem where you want to store reports from this run

`your_local_path_to_tests` - path on your local filesystem where you store jMeter tests

`test_type` - optional tag, used to filter test results

`env` - optional tag, used to filter test results

`loki_host` - loki host or IP, used to report failed requests to Loki

`loki_port` - optional, default 3100

`test_name` - name of the JMeter test file that will be run

`properties_file` - properties file name (described below)

`your_local_path_to_config/config.yaml` - config.yaml file with InfluxDB, Jira, Loki and Report Portal parameters (described below)

`JVM_ARGS` - Java heap params, like `-Xms1g -Xmx1g`



##### 3. Open test report
Report is located in your `your_local_path_to_reports` folder

### Configuration
Tests can be configured using `properties_file` file.

Config file example (parameters.txt):

```
influx.port=8086
influx.db=jmeter
influx.host=carrier_influx
comparison_db=comparison
lg.id=debug
DURATION=20
VUSERS=5
RAMP_UP=1
test_name=test
project.id=demo
test.type=demo
env.type=demo
```


You can also pass parameters from the command line with the -J option. For example :
```
... -t /mnt/jmeter/<test_name> -JVUSERS=1 -JRAMP_UP=1 ...
```

Error reporting can be configured using config.yaml file.

You can send aggregated errors to Report Portal or Jira. You can also send error info to Loki.

To do this, you need to uncomment the necessary configuration section and pass parameters.

**config.yaml** file example:
```
# Reporting configuration section (all report types are optional)
#reportportal:                                        # ReportPortal.io specific section
#  rp_host: https://rp.com                            # url to ReportPortal.io deployment
#  rp_token: XXXXXXXXXXXXX                            # ReportPortal authentication token
#  rp_project_name: XXXXXX                            # Name of a Project in ReportPortal to send results to
#  rp_launch_name: XXXXXX                             # Name of a launch in ReportPortal to send results to
#  check_functional_errors: False                     # Perform analysis by functional error. False or True (Default: False)
#  check_performance_degradation: False               # Perform analysis compared to baseline False or True (Default: False)
#  check_missed_thresholds: False                     # Perform analysis by exceeding thresholds False or True (Default: False)
#  performance_degradation_rate: 20                   # Minimum performance degradation rate at which to create a launch (Default: 20)
#  missed_thresholds_rate: 50                         # Minimum missed thresholds rate at which to create a launch (Default: 50)
#jira:
#  url: https://jira.com                              # Url to Jira
#  username: some.dude                                # User to create tickets
#  password: password                                 # password to user in Jira
#  jira_project: XYZC                                 # Jira project ID
#  assignee: some.dude                                # Jira id of default assignee
#  issue_type: Bug                                    # Jira issue type (Default: Bug)
#  labels: Performance, perfmeter                     # Comaseparated list of lables for ticket
#  watchers: another.dude                             # Comaseparated list of Jira IDs for watchers
#  jira_epic_key: XYZC-123                            # Jira epic key (or id)
#  check_functional_errors: False                     # Perform analysis by functional error False or True (Default: False)
#  check_performance_degradation: False               # Perform analysis compared to baseline False or True (Default: False)
#  check_missed_thresholds: False                     # Perform analysis by exceeding thresholds False or True (Default: False)
#  performance_degradation_rate: 20                   # Minimum performance degradation rate at which to create a JIRA ticket (Default: 20)
#  missed_thresholds_rate: 50                         # Minimum missed thresholds rate at which to create a JIRA ticket (Default: 50)#influx:
#  host: carrier_influx                               # Influx host DNS or IP
#  port: 8086                                         # Influx port (Default: 8086)
#  jmeter_db: jmeter                                  # Database name for jmeter test results (Default: jmeter)
#  comparison_db: comparison                          # Database name for comparison builds (Default: comparison)
#loki:
#  host: http://loki                                  # Loki host DNS or IP
#  port: 3100                                         # Loki port
```



### Jenkins pipeline

Carrier Perfmeter can be started inside Jenkins CI/CD pipeline.

Here is an example pipeline that will run demo test.

```
def get_influx_host(String env_var) {
    def match = env_var =~ 'http://(.+)/jenkins'
    return match[0][1]
}

node{
    stage("configure") {
        deleteDir()
        sh "mkdir reports"
    }
    stage("run tests") {
        def dockerParamsString = "--entrypoint=''"
        def params = [
            "-t"
        ]
        for (param in params) {
            dockerParamsString += " ${param}"
        }
        docker.image("getcarrier/perfmeter:1.0").inside(dockerParamsString){
            sh "mkdir /tmp/reports"
            sh "pwd"
            sh """cd / && ls -la &&  /launch.sh  -n -t /mnt/jmeter/FloodIO.jmx \\
                  -j /tmp/reports/jmeter_${JOB_NAME}_${BUILD_ID}.log \\
                  -l /tmp/reports/jmeter_${JOB_NAME}_${BUILD_ID}.jtl \\
                  -e -o /tmp/reports/HtmlReport_${JOB_NAME}_${BUILD_ID} \\
                  -Jinflux.host="""+get_influx_host(env.JENKINS_URL)+""" \\
                  -JVUSERS=10 -JDURATION=120 -Jinflux.db=jmeter -Jinflux.port=8086 \\
                  -JRAMP_UP=1 -Jtest_name=test -Jbuild.id=flood_io_${JOB_NAME}_${BUILD_ID} \\
                  -Jproject.id=demo -Jtest.type=demo -Jenv.type=demo"""
            sh "mv /tmp/reports/* ${WORKSPACE}/reports/"
        }
    }
    stage("publish results") {
        perfReport 'reports/*.jtl'
    }
}
```

In order to run your tests you need to copy your tests or clone your repository with the tests in the Jenkins workspace.

Then in the container launch command you need to specify the path to your tests (/launch.sh -n -t ${WORKSPACE}/<path_to_test>).

### Getting tests from object storage

You can upload your JMeter tests with all the necessary files (csv files, scripts) in ".zip" format to the Galloper artifacts.

Precondition for uploading tests is bucket availability in object storage

To create a bucket you should:

1. Open a galloper url in the browser e.g. `http://{{ galloper_url }}`
2. Click on  Artifacts in the side menu
3. Click on the Bucket icon in right side of the page and choose `Create New Bucket`
4. Name your bucket e.g. jmeter

Now you can upload your tests with all dependencies in ".zip" format.

In order to run the tests you can use the following command

```
docker run --rm -t -u 0:0 \
        -e galloper_url="http://{{ galloper_url }}" \
        -e bucket="jmeter" -e artifact="{{ file_with_your_tests.zip }}" \
        getcarrier/perfmeter:latest \
        -n -t /mnt/jmeter/{{ test_name }}.jmx \
        -Jinflux.host={{ influx_dns_or_ip }}
```

What it will do is copy saved artifact to `/mnt/jmeter/` folder and execute JMeter test `{{ test_name }}.jmx`

Also you can upload additional plugins/extensions to JMeter container using env variable `additional_files`

To do that you should upload your files to the Galloper artifacts and add env variable to the docker run command like this:

```
docker run --rm -t -u 0:0 \
       -e galloper_url="http://{{ galloper_url }}" \
       -e additional_files='{"jmeter/InfluxBackendListenerClient.jar": "/jmeter/apache-jmeter-5.0/lib/ext/InfluxBackendListenerClient.jar"}',
       getcarrier/perfmeter:latest \
       -n -t /mnt/jmeter/{{ test_name }}.jmx \
       -Jinflux.host={{ influx_dns_or_ip }}
```

It will copy `InfluxBackendListenerClient.jar` from `jmeter` bucket to container path `/jmeter/apache-jmeter-5.0/lib/ext/InfluxBackendListenerClient.jar`