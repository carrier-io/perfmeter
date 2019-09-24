import argparse
import redis
import json
import shutil

from error_parser import SimulationLogParser
from perfreporter.post_processor import PostProcessor


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
    parser.add_argument("-idb", "--influx_database", help='Comparison InfluxDB', default="jmeter")
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
    aggregated_errors, errors = logParser.parse_errors()

    if args['redis_connection']:
        test_info = logParser.prepare_test_results_for_redis()
        test_results = {"aggregated_errors": json.dumps(aggregated_errors), "errors": json.dumps(errors),
                        "test_info": json.dumps(test_info)}
        print(test_info)
        redis_client = redis.Redis.from_url(args['redis_connection'])
        redis_client.set("Test results " + str(args['lg_id']), json.dumps(test_results))
        redis_client.set("Arguments", json.dumps(args))

        zip_file = shutil.make_archive("/tmp/" + str(args['lg_id']), 'zip', RESULTS_FOLDER)
        if zip_file:
            with open(zip_file, 'rb') as f:
                redis_client.set("reports_" + str(args['lg_id']) + ".zip", f.read())
    else:
        post_processor = PostProcessor(args, aggregated_errors, errors)
        post_processor.post_processing()
