from influxdb import InfluxDBClient
import statistics


SELECT_LAST_BUILDS_ID = "select distinct(id) from (select build_id as id, pct95 from api_comparison where " \
                        "simulation=\'{}\' and test_type=\'{}\' and \"users\"=\'{}\' and build_id!~/baseline_id_{}/ " \
                        "order by time DESC) GROUP BY time(1s) order by DESC limit {}"

SELECT_BASELINE_BUILD_ID = "select last(pct95), build_id from api_comparison where simulation=\'{}\' and " \
                           "test_type=\'{}\' and \"users\"=\'{}\' and build_id=~/baseline_id_/"

SELECT_TEST_DATA = "select * from api_comparison where build_id=\'{}\' and lg_id=\'{}\'"

SELECT_BASELINE_DATA = "select * from api_comparison where build_id=\'{}\'"

SELECT_THRESHOLDS = "select last(red) as red, last(yellow) as yellow from threshold where request_name=\'{}\' " \
                    "and simulation=\'{}\'"


class DataManager:

    def __init__(self, arguments):
        self.args = arguments
        self.client = InfluxDBClient(arguments['influx_host'], arguments['influx_port'],
                                     username=arguments['influx_user'], password=arguments['influx_password'])
        self.last_build_data = None

    def compare_vs_baseline(self):
        test_data = self.get_last_build()
        if len(test_data) == 0:
            raise Exception("No data found for given parameters")
        baseline = self.get_baseline()
        if not baseline:
            print("Baseline not found")
            return 0, 1, []
        comparison_metric = self.args['comparison_metric']
        request_count = 0
        slower_then_baseline = 0
        compare_with_baseline = []
        for request in test_data:
            request_count += 1
            for baseline_request in baseline:
                if request['request_name'] == baseline_request['request_name']:
                    if int(request[comparison_metric]) > int(baseline_request[comparison_metric]):
                        slower_then_baseline += 1
                        compare_with_baseline.append({"request_name": request['request_name'],
                                                      "response_time": request[comparison_metric],
                                                      "baseline": baseline_request[comparison_metric],
                                                      })
        return slower_then_baseline, request_count, compare_with_baseline

    def get_last_build(self):
        if self.last_build_data:
            return self.last_build_data
        build_ids = []
        self.client.switch_database(self.args['influx_comparison_database'])
        last_builds = self.client.query(SELECT_LAST_BUILDS_ID.format(self.args['simulation'], self.args['type'],
                                                                     str(self.args['users']), self.args['build_id'],
                                                                     self.args['test_limit']))
        for test in list(last_builds.get_points()):
            if test['distinct'] not in build_ids:
                build_ids.append(test['distinct'])
        test_data = self.client.query(SELECT_TEST_DATA.format(build_ids[0], self.args['lg_id']))
        self.last_build_data = list(test_data.get_points())
        return self.last_build_data

    def get_baseline(self):
        self.client.switch_database(self.args['influx_comparison_database'])
        baseline_build_id = self.client.query(SELECT_BASELINE_BUILD_ID.format(self.args['simulation'], self.args['type'],
                                                                              str(self.args['users'])))
        result = list(baseline_build_id.get_points())
        if len(result) == 0:
            return None
        _id = result[0]['build_id']
        baseline_data = self.client.query(SELECT_BASELINE_DATA.format(_id))
        self.client.close()
        baseline_data = self.aggregate_api_test_results([baseline_data])
        return baseline_data[0]

    @staticmethod
    def aggregate_api_test_results(tests_data):
        tests = []
        for test in tests_data:
            test_info = []
            request_names = []
            for request in list(test.get_points()):
                if request['request_name'] not in request_names:
                    request_names.append(request['request_name'])
            for request_name in request_names:
                request_info = {}
                for request in list(test.get_points()):
                    if request_name == request['request_name']:
                        if request['request_name'] in request_info.values():
                            request_info['1xx'] = int(request_info['1xx']) + request['1xx']
                            request_info['2xx'] = int(request_info['2xx']) + request['2xx']
                            request_info['3xx'] = int(request_info['3xx']) + request['3xx']
                            request_info['4xx'] = int(request_info['4xx']) + request['4xx']
                            request_info['5xx'] = int(request_info['5xx']) + request['5xx']
                            request_info['NaN'] = int(request_info['NaN']) + request['NaN']
                            request_info['ko'] = int(request_info['ko']) + request['ko']
                            request_info['ok'] = int(request_info['ok']) + request['ok']
                            request_info['total'] = int(request_info['total']) + request['total']
                            request_info['max_array'].append(int(request['max']))
                            request_info['min_array'].append(int(request['min']))
                            request_info['mean_array'].append(int(request['mean']))
                            request_info['pct50_array'].append(int(request['pct50']))
                            request_info['pct75_array'].append(int(request['pct75']))
                            request_info['pct90_array'].append(int(request['pct90']))
                            request_info['pct95_array'].append(int(request['pct95']))
                            request_info['pct99_array'].append(int(request['pct99']))
                            request_info['throughput_array'].append(int(request['throughput']))
                        else:
                            request_info = request
                            request_info['max_array'] = [int(request_info['max'])]
                            request_info['min_array'] = [int(request_info['min'])]
                            request_info['mean_array'] = [int(request_info['mean'])]
                            request_info['pct50_array'] = [int(request_info['pct50'])]
                            request_info['pct75_array'] = [int(request_info['pct75'])]
                            request_info['pct90_array'] = [int(request_info['pct90'])]
                            request_info['pct95_array'] = [int(request_info['pct95'])]
                            request_info['pct99_array'] = [int(request_info['pct99'])]
                            request_info['throughput_array'] = [int(request_info['throughput'])]

                request_info['max'] = int(statistics.median(request_info['max_array']))
                request_info['min'] = int(statistics.median(request_info['min_array']))
                request_info['mean'] = int(statistics.median(request_info['mean_array']))
                request_info['pct50'] = int(statistics.median(request_info['pct50_array']))
                request_info['pct75'] = int(statistics.median(request_info['pct75_array']))
                request_info['pct90'] = int(statistics.median(request_info['pct90_array']))
                request_info['pct95'] = int(statistics.median(request_info['pct95_array']))
                request_info['pct99'] = int(statistics.median(request_info['pct99_array']))
                request_info['throughput'] = int(statistics.median(request_info['throughput_array']))
                test_info.append(request_info)

            tests.append(test_info)
        return tests

    def compare_vs_thresholds(self):
        test_data = self.get_last_build()
        if len(test_data) == 0:
            raise Exception("No data found for given parameters")
        test_data = self.append_api_thresholds_to_test_data(test_data)
        request_count, missed_thresholds = 0, 0
        compare_with_thresholds = []
        comparison_metric = self.args['comparison_metric']
        for request in test_data:
            request_count += 1
            if request[comparison_metric + '_threshold'] is not 'green':
                missed_thresholds += 1
                compare_with_thresholds.append({"request_name": request['request_name'],
                                                "response_time": request[comparison_metric],
                                                "threshold": request[comparison_metric + '_threshold'],
                                                "yellow": request['yellow_threshold_value'],
                                                "red": request["red_threshold_value"]})

        return missed_thresholds, request_count, compare_with_thresholds

    def append_api_thresholds_to_test_data(self, test):
        self.client.switch_database(self.args['influx_thresholds_database'])
        params = ['request_name', 'total', 'throughput', 'ko', 'min', 'max', 'pct50', 'pct75', 'pct95', 'time',
                  'simulation', 'users', 'duration']
        test_summary = []
        for request in test:
            request_data = {}
            comparison_metric = self.args['comparison_metric']
            threshold = self.client.query(SELECT_THRESHOLDS.format(str(request['request_name']),
                                                                   str(request['simulation'])))
            if len(list(threshold.get_points())) == 0:
                red_threshold = 3000
                yellow_threshold = 2000
            else:
                red_threshold = int(list(threshold.get_points())[0]['red'])
                yellow_threshold = int(list(threshold.get_points())[0]['yellow'])

            if int(request[comparison_metric]) < yellow_threshold:
                request_data[comparison_metric + '_threshold'] = 'green'
            else:
                request_data[comparison_metric + '_threshold'] = 'yellow'
            if int(request[comparison_metric]) >= red_threshold:
                request_data[comparison_metric + '_threshold'] = 'red'
            request_data['yellow_threshold_value'] = yellow_threshold
            request_data['red_threshold_value'] = red_threshold
            for param in params:
                request_data[param] = request[param]
            test_summary.append(request_data)
        return test_summary
