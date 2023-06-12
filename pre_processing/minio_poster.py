import argparse
import json
import shutil
from os import environ
import requests


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
    if environ.get("report_id"):
        args["report_id"] = environ.get("report_id")

    prefix = environ.get('DISTRIBUTED_MODE_PREFIX')
    save_reports = environ.get('save_reports')
    token = environ.get('token')
    integrations = json.loads(environ.get("integrations", '{}'))
    s3_config = integrations.get('system', {}).get('s3_integration', {})

    if prefix:
        PROJECT_ID = environ.get('project_id')
        URL = environ.get('galloper_url')
        BUCKET = environ.get("results_bucket")
        if not all(a for a in [URL, BUCKET]):
            exit(0)

        # Make archive with data for post processing
        with open(DATA_FOR_POST_PROCESSING_FOLDER + "args.json", 'w') as f:
            f.write(json.dumps(args))
        with open(DATA_FOR_POST_PROCESSING_FOLDER + "aggregated_errors.json", 'w') as f:
            f.write(json.dumps({}))
        path_to_test_results = "/tmp/" + prefix + "_" + str(args['lg_id'])
        shutil.make_archive(path_to_test_results, 'zip', DATA_FOR_POST_PROCESSING_FOLDER)

        # Send data to minio
        headers = {'Authorization': f'bearer {token}'} if token else {}
        upload_url = f'{URL}/api/v1/artifacts/artifacts/{PROJECT_ID}/{BUCKET}'
        requests.post(f'{URL}/api/v1/artifacts/buckets/{PROJECT_ID}', params=s3_config, 
                      allow_redirects=True, data={'name': BUCKET},
                      headers={**headers, 'Content-type': 'application/json'})
        files = {'file': open(path_to_test_results + ".zip", 'rb')}

        requests.post(upload_url, params=s3_config, allow_redirects=True, files=files, headers=headers)
