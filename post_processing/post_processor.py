import argparse
import json
import shutil
from os import environ, path, listdir
import requests
from perfreporter.post_processor import PostProcessor
from perfreporter.error_parser import ErrorLogParser


RESULTS_FOLDER = '/tmp/reports/'

DATA_FOR_POST_PROCESSING_FOLDER = "/tmp/data_for_post_processing/"


def get_args():
    parser = argparse.ArgumentParser(description='Simlog parser.')
    parser.add_argument("-t", "--type", help="Test type.")
    parser.add_argument("-s", "--simulation", help='Test simulation', default=None)
    parser.add_argument("-b", "--build_id", help="build ID", default=None)
    parser.add_argument("-en", "--env", help="Test type.", default=None)
    parser.add_argument("-i", "--influx_host", help='InfluxDB host or IP', default=None)
    parser.add_argument("-p", "--influx_port", help='InfluxDB port', default=8086)
    parser.add_argument("-iu", "--influx_user", help='InfluxDB user', default="")
    parser.add_argument("-ip", "--influx_password", help='InfluxDB password', default="")
    parser.add_argument("-cm", "--comparison_metric", help='Comparison metric', default="pct95")
    parser.add_argument("-idb", "--influx_db", help='Test results InfluxDB', default="jmeter")
    parser.add_argument("-icdb", "--comparison_db", help='Comparison InfluxDB', default="comparison")
    parser.add_argument("-itdb", "--thresholds_db", help='Thresholds InfluxDB', default="thresholds")
    parser.add_argument("-tl", "--test_limit", help='test_limit', default=5)
    parser.add_argument("-l", "--lg_id", help='Load generator ID', default=None)
    parser.add_argument("-el", "--error_logs", help='Path to the error logs', default='/tmp/')
    return vars(parser.parse_args())


if __name__ == '__main__':
    args = get_args()
    logParser = ErrorLogParser(args)
    aggregated_errors = logParser.parse_errors()
    prefix = environ.get('DISTRIBUTED_MODE_PREFIX')
    if prefix:
        URL = environ.get('galloper_url')
        BUCKET = environ.get("results_bucket")
        if not all(a for a in [URL, BUCKET]):
            exit(0)

        # Make archive with jmeter reports
        path_to_reports = "/tmp/reports_" + prefix + "_" + str(args['lg_id'])
        shutil.make_archive(path_to_reports, 'zip', RESULTS_FOLDER)

        # Make archive with data for post processing
        with open(DATA_FOR_POST_PROCESSING_FOLDER + "args.json", 'w') as f:
            f.write(json.dumps(args))
        with open(DATA_FOR_POST_PROCESSING_FOLDER + "aggregated_errors.json", 'w') as f:
            f.write(json.dumps(aggregated_errors))
        path_to_test_results = "/tmp/" + prefix + "_" + str(args['lg_id'])
        shutil.make_archive(path_to_test_results, 'zip', DATA_FOR_POST_PROCESSING_FOLDER)

        # Send data to minio
        create_bucket = requests.post(f'{URL}/artifacts/bucket', allow_redirects=True, data={'bucket': BUCKET})
        files = {'file': open(path_to_reports + ".zip", 'rb')}
        requests.post(f'{URL}/artifacts/{BUCKET}/upload', allow_redirects=True, files=files)
        files = {'file': open(path_to_test_results + ".zip", 'rb')}
        requests.post(f'{URL}/artifacts/{BUCKET}/upload', allow_redirects=True, files=files)
    else:
        print("[INFO] Post processing started")
        # Check if the folder exists
        if path.exists(RESULTS_FOLDER):
            # List the contents of the folder
            folder_contents = listdir(RESULTS_FOLDER)
        
            # Print the list of contents
            print("Contents of the folder:")
            for item in folder_contents:
                print(item)
        else:
            print("The specified folder does not exist.")
        post_processor = PostProcessor()
        post_processor.post_processing(args, aggregated_errors)
