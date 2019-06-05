# perfmeter
*Carrier customized jMeter container*

### Quick and easy start
These simple steps will run jMeter test against your application and generate html and jtl report.

##### 1. Install docker

##### 2. Start container and pass the necessary config options to container and mount reports folder:
`your_local_path_to_reports` - path on your local filesystem where you want to store reports from this 

`your_local_path_to_tests` - path on your local filesystem where you store jMeter tests

`test_name` - name of the jMeter test file that will be run

`properties_file` - properties file name

`your_local_path_to_config/config.yaml` - config.yaml file with InfluxDB, Jira and Report Portal parameters (described below)

For example:

``` 
docker run --rm -u 0:0 \
       -v <your_local_path_to_tests>:/mnt/jmeter/ \
       -v <your_local_path_to_config/config.yaml>:/tmp/ #optional
       -v <your_local_path_to_reports>:/tmp/reports \   #optional
       getcarrier/perfmeter:latest \
       -n -t /mnt/jmeter/<test_name> 
       -q /mnt/jmeter/<properties_file> \    #optional
       -j /tmp/reports/jmeter_$(date +%s).log \  #optional
       -l /tmp/reports/jmeter_$(date +%s).jtl -e \  # optional
       -o /tmp/reports/HtmlReport_$(date +%s)/    #optional
```

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

Reporting can be configured using config.yaml file.

You have to uncomment the necessary configuration section and pass parameters to use it in your test

**config.yaml** file example:
```
# Reporting configuration section (all report types are optional)
#reportportal:                                        # ReportPortal.io specific section
#  rp_host: https://rp.com                            # url to ReportPortal.io deployment
#  rp_token: XXXXXXXXXXXXX                            # ReportPortal authentication token
#  rp_project_name: XXXXXX                            # Name of a Project in ReportPortal to send results to
#  rp_launch_name: XXXXXX                             # Name of a launch in ReportPortal to send results to
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
#influx:
#  host: carrier_influx                               # Influx host DNS or IP
#  port: 8086                                         # Influx port (Default: 8086)
#  jmeter_db: jmeter                                  # Database name for jmeter test results (Default: jmeter)
#  comparison_db: comparison                          # Database name for comparison builds (Default: comparison)
```
