import argparse
import json
import shutil
import os
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
    try:
        aggregated_errors = logParser.parse_errors()
    except Exception as e:
        aggregated_errors = {}

    prefix = os.environ.get('DISTRIBUTED_MODE_PREFIX')
    save_reports = True if os.environ.get('save_reports') == "True" else False
    token = os.environ.get('token')
    if prefix:
        PROJECT_ID = os.environ.get('project_id')
        URL = os.environ.get('galloper_url')
        BUCKET = os.environ.get("results_bucket")
        if not all(a for a in [URL, BUCKET]):
            exit(0)

        # Make archive with jmeter reports
        path_to_reports = "/tmp/reports_" + prefix + "_" + str(args['lg_id'])
        shutil.make_archive(path_to_reports, 'zip', RESULTS_FOLDER)

        # Remove tmp files
        path_to_test_results = "/tmp/" + prefix + "_" + str(args['lg_id'])
        if os.path.exists(path_to_test_results + ".zip"):
            os.remove(path_to_test_results + ".zip")
        if os.path.exists(DATA_FOR_POST_PROCESSING_FOLDER + "args.json"):
            os.remove(DATA_FOR_POST_PROCESSING_FOLDER + "args.json")
        if os.path.exists(DATA_FOR_POST_PROCESSING_FOLDER + "aggregated_errors.json"):
            os.remove(DATA_FOR_POST_PROCESSING_FOLDER + "aggregated_errors.json")

        # Make archive with data for post processing
        with open(DATA_FOR_POST_PROCESSING_FOLDER + "args.json", 'w') as f:
            f.write(json.dumps(args))
        with open(DATA_FOR_POST_PROCESSING_FOLDER + "aggregated_errors.json", 'w') as f:
            f.write(json.dumps(aggregated_errors))
        path_to_test_results = "/tmp/" + prefix + "_" + str(args['lg_id'])
        shutil.make_archive(path_to_test_results, 'zip', DATA_FOR_POST_PROCESSING_FOLDER)

        # Send data to minio
        headers = {'Authorization': f'bearer {token}'} if token else {}
        if PROJECT_ID:
            upload_url = f'{URL}/api/v1/artifacts/{PROJECT_ID}/{BUCKET}/file'
            requests.post(f'{URL}/api/v1/artifacts/{PROJECT_ID}/{BUCKET}', allow_redirects=True, headers=headers)
        else:
            upload_url = f'{URL}/artifacts/{BUCKET}/upload'
            requests.post(f'{URL}/artifacts/bucket', allow_redirects=True, data={'bucket': BUCKET}, headers=headers)
        files = {'file': open(path_to_test_results + ".zip", 'rb')}

        requests.post(upload_url, allow_redirects=True, files=files, headers=headers)
        if save_reports:
            files = {'file': open(path_to_reports + ".zip", 'rb')}
            requests.post(upload_url, allow_redirects=True, files=files, headers=headers)

    else:
        post_processor = PostProcessor()
        post_processor.post_processing(args, aggregated_errors)
