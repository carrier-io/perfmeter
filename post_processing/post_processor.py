#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import redis
import json
import shutil

from data_manager import DataManager
from error_parser import SimulationLogParser
from perfreporter.reporter import Reporter


RESULTS_FOLDER = '/tmp/reports/'


def get_args():
    parser = argparse.ArgumentParser(description='Simlog parser.')
    parser.add_argument("-f", "--file", help="file path", default=None)
    parser.add_argument("-r", "--redis_connection", help="redis_connection", default=None)
    parser.add_argument("-t", "--type", help="Test type.")
    parser.add_argument("-b", "--build_id", help="build ID", default=None)
    parser.add_argument("-s", "--simulation", help='Test simulation', default=None)
    parser.add_argument("-st", "--start_time", help='Test start time', default=None)
    parser.add_argument("-et", "--end_time", help='Test end time', default=None)
    parser.add_argument("-i", "--influx_host", help='InfluxDB host or IP', default=None)
    parser.add_argument("-p", "--influx_port", help='InfluxDB port', default=None)
    parser.add_argument("-iu", "--influx_user", help='InfluxDB user', default="")
    parser.add_argument("-ip", "--influx_password", help='InfluxDB password', default="")
    parser.add_argument("-cm", "--comparison_metric", help='Comparison metric', default="pct95")
    parser.add_argument("-icdb", "--influx_comparison_database", help='Comparison InfluxDB', default="comparison")
    parser.add_argument("-itdb", "--influx_thresholds_database", help='Thresholds InfluxDB', default="thresholds")
    parser.add_argument("-u", "--users", help='Users count', default=None)
    parser.add_argument("-tl", "--test_limit", help='test_limit', default=5)
    parser.add_argument("-l", "--lg_id", help='Load generator ID', default=None)
    return vars(parser.parse_args())


if __name__ == '__main__':
    args = get_args()
    print("Parsing functional errors ...")
    logParser = SimulationLogParser(args)
    aggregated_errors, errors = logParser.parse_log()

    data_manager = DataManager(args)
    print("Checking performance degradation ...")
    slower_then_baseline, request_count, compare_with_baseline = data_manager.compare_vs_baseline()
    performance_degradation_rate = round(float(slower_then_baseline / request_count) * 100, 2)

    print("Checking missed thresholds ...")
    missed_thresholds, request_count, compare_with_thresholds = data_manager.compare_vs_thresholds()
    missed_threshold_rate = round(float(missed_thresholds / request_count) * 100, 2)

    if args['redis_connection']:
        test_results = {"aggregated_errors": json.dumps(aggregated_errors), "errors": json.dumps(errors),
                        "compare_with_baseline": json.dumps(compare_with_baseline),
                        "compare_with_thresholds": json.dumps(compare_with_thresholds)}
        redis_client = redis.Redis.from_url(args['redis_connection'])
        redis_client.set("Test results " + str(args['lg_id']), json.dumps(test_results))
        redis_client.set("build_id", args['build_id'])
        redis_client.set("request_count", request_count)
        redis_client.set("comparison_metric", args['comparison_metric'])
        redis_client.set("test_type", args['type'])
        redis_client.set("simulation", args['simulation'])

        zip_file = shutil.make_archive("/tmp/" + str(args['lg_id']), 'zip', RESULTS_FOLDER)
        if zip_file:
            with open(zip_file, 'rb') as f:
                redis_client.set("reports_" + str(args['lg_id']) + ".zip", f.read())
    else:
        reporter = Reporter()
        print("Parsing config file ...")
        loki, rp_service, jira_service = reporter.parse_config_file(args)
        if any([loki, rp_service, jira_service]):
            reporter.report_errors(aggregated_errors, errors, args, loki, rp_service, jira_service)
            reporter.report_performance_degradation(performance_degradation_rate, compare_with_baseline, rp_service,
                                                    jira_service)
            reporter.report_missed_thresholds(missed_threshold_rate, compare_with_thresholds, rp_service, jira_service)
        else:
            print("Reporting channels are not set up. Please check config.yaml file.")
