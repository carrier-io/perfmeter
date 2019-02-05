from time import time
import datetime
import numpy as np
from influxdb import InfluxDBClient

COMPARISON_DATABASE = 'comparison'


class TestResultsParser(object):
    def __init__(self, arguments):
        self.args = arguments

    def parse_results(self):
        """Parse test results and send to comparison database"""
        simulation = self.args['simulation']
        reqs = dict()
        test_time = time()
        build_id = "{}_{}_{}".format(self.args['test.type'], self.args['VUSERS'],
                                     datetime.datetime.fromtimestamp(test_time).strftime('%Y-%m-%dT%H:%M:%SZ'))
        client = InfluxDBClient(self.args["influx.host"], self.args["influx.port"], username='', password='',
                                database=self.args["influx.db"])
        results = client.query("SELECT * FROM requestsRaw where time >= " + str(self.args['start_time'])
                               + "ms and time <= " + str(self.args['end_time']) + "ms")
        client.close()
        for entry in list(results.get_points()):
            try:
                data = {'simulation': simulation, 'test_type': self.args['test.type'],
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
                    "users": self.args['VUSERS'],
                    "test_type": self.args["test.type"],
                    "build_id": build_id,
                    "request_name": reqs[req]['request_name'],
                    "method": reqs[req]['method'],
                    "duration": self.args['DURATION']
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


def parse_args():
    args = {}
    with open("/mnt/jmeter/parameters.txt") as file:
        for line in file:
            split = line.split("=")
            args[split[0]] = split[1].replace("\n", "")
    if 'VUSERS' not in args:
        args['VUSERS'] = 1
    if 'test.type' not in args:
        args['test.type'] = 'demo'
    if 'DURATION' not in args:
        args['DURATION'] = 10
    if 'influx.host' not in args or 'influx.port' not in args or 'influx.db' not in args:
        print("InfluxDB config not found in parameters.txt. Exit")
        exit(0)
    return args


if __name__ == '__main__':
    print("Parsing simulation log")
    args = parse_args()
    testResultsParser = TestResultsParser(args)
    testResultsParser.parse_results()
