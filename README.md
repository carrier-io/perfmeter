# perfmeter
*Carrier customized jMeter container*

### Quick and easy start
These simple steps will run jMeter test against your application and generate html and jtl report.

##### 1. Install docker

##### 2. Start container and pass the necessary config options to container and mount reports folder:
`your_local_path_to_reports` - path on your local filesystem where you want to store reports from this 

`your_local_path_to_tests` - path on your local filesystem where you store jMeter tests

`test_name` - name of the jMeter test file that will be run

`config_file` - config file name

For example:

``` 
docker run --rm\
       -v <your_local_path_to_tests>:/mnt/jmeter/ \
       -v <your_local_path_to_reports>:/tmp/reports \  - optional
       getcarrier/perfmeter:latest \
       -n -t /mnt/jmeter/<test_name> 
       -q /mnt/jmeter/<config_file> \   - optional
       -j /tmp/reports/jmeter_$(date +%s).log \  - optional
       -l /tmp/reports/jmeter_$(date +%s).jtl -e \  - optional
       -o /tmp/reports/HtmlReport_$(date +%s)/   - optional
```

##### 3. Open test report
Report is located in your `your_local_path_to_reports` folder

### Configuration
Tests can be configured using `config_file` file.

Config file example (parameters.txt):

```
influx.port=8086
influx.db=jmeter
lg.id=debug
LOOP_COUNT=1
VUSERS=1
RAMP_UP=1
simulation=TEST
build.id=1
project.id=TEST
influx.host=<influx_host>
test.type=TEST
env.type=TEST
```


You can also pass parameters from the command line with the -J option. For example :
```
... -t /mnt/jmeter/<test_name> -JVUSERS=1 -JRAMP_UP=1 ...
```
