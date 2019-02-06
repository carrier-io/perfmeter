from time import time
import datetime
import numpy as np
import sys
from influxdb import InfluxDBClient

COMPARISON_DATABASE = 'comparison'


class TestResultsParser(object):
    def __init__(self, arguments):
        self.args = arguments

    def parse_results(self):
        """Parse test results and send to comparison database"""
        simulation = self.args['test_name']
        reqs = dict()
        test_time = time()
        client = InfluxDBClient(self.args["influx.host"], self.args["influx.port"], username='', password='',
                                database=self.args["influx.db"])
        raws = client.query("SELECT * FROM virtualUsers WHERE simulation=\'" + simulation +
                            "\' and time >= " + str(self.args['start_time']) + "ms and time <= "
                            + str(self.args['end_time']) + "ms LIMIT 1")
        for raw in list(raws.get_points()):
            users = raw['startedThreads']
            test_type = raw['testType']
        build_id = "{}_{}_{}".format(test_type, users,
                                     datetime.datetime.fromtimestamp(test_time).strftime('%Y-%m-%dT%H:%M:%SZ'))
        results = client.query("SELECT * FROM requestsRaw WHERE simulation=\'" + simulation +
                               "\' and time >= " + str(self.args['start_time']) + "ms and time <= "
                               + str(self.args['end_time']) + "ms")
        client.close()
        for entry in list(results.get_points()):
            try:
                data = {'simulation': simulation, 'test_type': entry['testType'],
                        'response_time': int(entry['responseTime']), 'request_name': entry['requestName'],
                        'response_code': entry['responseCode'], 'request_url': str(entry['url']),
                        'request_method': str(entry['method']), 'status': str(entry['status'])}
                key = '{} {}'.format(data["request_method"].upper(), data["request_name"])
                if key not in reqs:
                    reqs[key] = {
                        "times": [],
                        "KO": 0,
                        "OK": 0,
                        "1xx": 0,
                        "2xx": 0,
                        "3xx": 0,
                        "4xx": 0,
                        "5xx": 0,
                        'NaN': 0,
                        "method": data["request_method"].upper(),
                        "request_name": data['request_name']
                    }
                reqs[key]['times'].append(data['response_time'])
                if "{}xx".format(str(data['response_code'])[0]) in reqs[key]:
                    reqs[key]["{}xx".format(str(data['response_code'])[0])] += 1
                else:
                    reqs[key]["NaN"] += 1
                reqs[key][data['status']] += 1
            except:
                pass
        if not reqs:
            exit(0)
        points = []
        for req in reqs:
            np_arr = np.array(reqs[req]["times"])
            influx_record = {
                "measurement": "api_comparison",
                "tags": {
                    "simulation": simulation,
                    "users": users,
                    "test_type": test_type,
                    "build_id": build_id,
                    "request_name": reqs[req]['request_name'],
                    "method": reqs[req]['method'],
                    "duration": int(self.args['end_time'])/1000 - int(self.args['start_time'])/1000
                },
                "time": datetime.datetime.fromtimestamp(test_time).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "fields": {
                    "throughput": round(float(len(reqs[req]["times"])*1000)/float(int(self.args['end_time'])-int(self.args['start_time'])), 3),
                    "total": len(reqs[req]["times"]),
                    "ok": reqs[req]["OK"],
                    "ko": reqs[req]["KO"],
                    "1xx": reqs[req]["1xx"],
                    "2xx": reqs[req]["2xx"],
                    "3xx": reqs[req]["3xx"],
                    "4xx": reqs[req]["4xx"],
                    "5xx": reqs[req]["5xx"],
                    "NaN": reqs[req]["NaN"],
                    "min": round(np_arr.min(), 2),
                    "max": round(np_arr.max(), 2),
                    "mean": round(np_arr.mean(), 2),
                    "pct50": np.percentile(np_arr, 50, interpolation="higher"),
                    "pct75": np.percentile(np_arr, 75, interpolation="higher"),
                    "pct90": np.percentile(np_arr, 90, interpolation="higher"),
                    "pct95": np.percentile(np_arr, 95, interpolation="higher"),
                    "pct99": np.percentile(np_arr, 99, interpolation="higher")
                }

            }
            points.append(influx_record)
        client = InfluxDBClient(self.args["influx.host"], self.args["influx.port"], username='', password='',
                                database=COMPARISON_DATABASE)
        client.write_points(points)
        client.close()


def parse_args(jmeter_execution_string):
    args = {}
    try:
        path = jmeter_execution_string.split("-q%")[1].split(".txt")[0] + ".txt"
        with open(path) as file:
            for line in file:
                split = line.split("=")
                args[split[0]] = split[1].replace("\n", "")
    except:
        pass
    params = jmeter_execution_string.split("%")
    for param in params:
        if str(param).__contains__("-J"):
            key = param.split("=")[0]
            args[str(key)[2:]] = param.split("=")[1]
    if 'influx.host' not in args:
        print("InfluxDB in not configured. Exit")
        exit(0)
    if 'influx.port' not in args:
        args['influx.port'] = 8086
    if 'influx.db' not in args:
        args['influx.db'] = 'jmeter'
    with open("/mnt/jmeter/test_info.txt") as file:
        for line in file:
            split = line.split("=")
            args[split[0]] = split[1].replace("\n", "")
    if 'test_name' not in args:
        args['test_name'] = 'test'
    return args


if __name__ == '__main__':
    print("Parsing simulation log")
    jmeter_execution_string = sys.argv[1]
    args = parse_args(jmeter_execution_string)
    testResultsParser = TestResultsParser(args)
    testResultsParser.parse_results()
