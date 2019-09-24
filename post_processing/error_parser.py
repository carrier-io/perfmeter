import csv
from difflib import SequenceMatcher
import datetime
import re


UNDEFINED = "undefined"
FIELDNAMES = 'action', 'simulation', 'thread', "simulation_name", "request_name", \
             "request_start", "request_end", "status", "error_message", "error"
ERROR_FIELDS = 'Response', 'Request_params', 'Error_message'


class SimulationLogParser(object):
    def __init__(self, arguments):
        self.args = arguments

    def parse_errors(self):
        """Parse line with error and send to database"""
        simulation = self.args['simulation']
        path = self.args['file']
        unparsed_counter = 0
        aggregated_errors = {}
        errors = []
        with open(path, 'r+', encoding="utf-8") as tsv:
            for entry in csv.DictReader(tsv, delimiter="\t", fieldnames=FIELDNAMES, restval="not_found"):
                if len(entry) >= 8 and (entry['status'] == "KO"):
                    try:
                        data = self.parse_entry(entry)
                        data['simulation'] = simulation
                        data["request_params"] = self.remove_session_id(data["request_params"])
                        request_start = datetime.datetime.utcfromtimestamp(int(data['request_start']) / 1000000000) \
                                                .strftime('%Y-%m-%d %H:%M:%S')
                        key = "%s_%s_%s" % (data['request_name'], data['request_method'], data['response_code'])
                        errors.append({"Request name": data['request_name'], "Method": data['request_method'],
                                       "Request headers": data["headers"], 'Time': request_start,
                                       "Response code": data['response_code'], "Error code": data['error_code'],
                                       "Request URL": data['request_url'],
                                       "Request_params": data['request_params'], "Response": data['response'],
                                       "Error_message": data['error_message'], "error_key": key})
                        count = 1
                        key = "%s_%s_%s" % (data['request_name'], data['request_method'], data['response_code'])
                        if key not in aggregated_errors:
                            aggregated_errors[key] = {"Request name": data['request_name'], "Method": data['request_method'],
                                           "Request headers": data["headers"], 'Error count': count,
                                           "Response code": data['response_code'], "Error code": data['error_code'],
                                           "Request URL": data['request_url'],
                                           "Request_params": [data['request_params']], "Response": [data['response']],
                                           "Error_message": [data['error_message']]}
                        else:
                            aggregated_errors[key]['Error count'] += 1
                            for field in ERROR_FIELDS:
                                same = self.check_dublicate(aggregated_errors[key], data, field)
                                if same is True:
                                    break
                                else:
                                    aggregated_errors[key][field].append(data[field.lower()])
                    except Exception as e:
                        print(e)
                        unparsed_counter += 1
                        pass

        if unparsed_counter > 0:
            print("Unparsed errors: %d" % unparsed_counter)
        return aggregated_errors, errors

    def prepare_test_results_for_redis(self):
        path = self.args['file']
        reqs = dict()
        user_count = 0 if self.args['users'] is None else int(self.args['users'])
        with open(path, 'r+', encoding="utf-8") as tsv:
            for entry in csv.DictReader(tsv, delimiter="\t", fieldnames=FIELDNAMES, restval="not_found"):
                if entry['action'] == "REQUEST":
                    try:
                        data = self.parse_data(entry)
                        key = '{} {}'.format(data["request_method"].upper(), data["request_name"])
                        if key not in reqs:
                            reqs[key] = {
                                "total": 0,
                                "KO": 0,
                                "OK": 0,
                                "1xx": 0,
                                "2xx": 0,
                                "3xx": 0,
                                "4xx": 0,
                                "5xx": 0,
                                'NaN': 0,
                                "method": data["request_method"].upper(),
                                "request_name": data['request_name'],
                                "users": user_count,
                                "duration": int(self.args['end_time']) / 1000 - int(self.args['start_time']) / 1000,
                                "simulation": self.args['simulation'],
                                "test_type": self.args["type"],
                                "build_id": self.args['build_id']
                            }
                        if "{}xx".format(str(data['response_code'])[0]) in reqs[key]:
                            reqs[key]["{}xx".format(str(data['response_code'])[0])] += 1
                        else:
                            reqs[key]["NaN"] += 1
                        reqs[key][data['status']] += 1
                        reqs[key]['total'] += 1
                    except:
                        pass
        return reqs

    @staticmethod
    def check_dublicate(entry, data, field):
        for params in entry[field]:
            if SequenceMatcher(None, str(data[field.lower()]), str(params)).ratio() > 0.7:
                return True

    def parse_data(self, values):
        """Parse error entry"""
        values['test_type'] = self.args['type']
        values['response_time'] = int(values['request_end']) - int(values['request_start'])
        values['response_code'] = self.extract_response_code(values['error'])
        values['request_url'], _, values['request_method'] = self.parse_request(values['error'])
        return values

    def parse_entry(self, values):
        """Parse error entry"""
        values['test_type'] = self.args['type']
        values['response_time'] = int(values['request_end']) - int(values['request_start'])
        values['request_start'] += "000000"
        values['response_code'] = self.extract_response_code(values['error'])
        values['error_code'] = self.extract_error_code(values['error'])
        values['request_url'], values['request_params'], values['request_method'] = self.parse_request(values['error'])
        values['headers'] = self.html_decode(self.escape_for_json(self.parse_headers(values['error'])))
        values['response'] = self.html_decode(self.parse_response(values['error']))
        values['error'] = self.escape_for_json(values['error'])
        values['error_message'] = self.escape_for_json(values['error_message'])

        return values

    def extract_error_code(self, error_code):
        """Extract code of error from response body"""
        error_code_regex = re.search(r'("code"|"Code"): ?"?(-?\d+)"?,', error_code)
        if error_code_regex and error_code_regex.group(2):
            return error_code_regex.group(2)
        return UNDEFINED

    def remove_session_id(self, param):
        sessionid_regex = re.search(r'(SessionId|sessionID|sessionId|SessionID)=(.*?&|.*)', param)
        if sessionid_regex and sessionid_regex.group(2):
            return param.replace(sessionid_regex.group(2), '_...')
        return param

    def extract_response_code(self, error):
        """Extract response code"""
        code_regexp = re.search(r"HTTP Code: ?([a-zA-Z]*?\(?(\d+)\)?),", error)
        if code_regexp and code_regexp.group(2):
            return code_regexp.group(2)
        return UNDEFINED

    def html_decode(self, s):
        html_codes = (
            ("'", '&#39;'),
            ("/", '&#47;'),
            ('"', '&quot;'),
            (':', '%3A'),
            ('/', '%2F'),
            ('.', '%2E'),
            ('&', '&amp;'),
            ('>', '&gt;'),
            ('|', '%7C'),
            ('<', '&lt;'),
            ('\\"', '"')
        )
        for code in html_codes:
            s = s.replace(code[1], code[0])
        return s

    def escape_for_json(self, string):
        if isinstance(string, str):
            return string.replace('"', '&quot;') \
                .replace("\\", "&#92;") \
                .replace("/", "&#47;") \
                .replace("<", "&lt;") \
                .replace(">", "&gt;")
        return string

    def parse_request(self, param):
        regex = re.search(r"Request: ?(.+?) ", param)
        if regex and regex.group(1):
            request_parts = regex.group(1).split("?")
            url = request_parts[0]
            params = request_parts[len(request_parts) - 1] if len(request_parts) >= 2 else ''
            params = params + " " + self.parse_params(param)
            params = params.replace(":", "=")
            url = self.html_decode(self.escape_for_json(url))
            params = self.escape_for_json(params)
            method = re.search(r" ([A-Z]+) headers", param).group(1)
            return url, params, method
        return UNDEFINED, UNDEFINED, UNDEFINED

    def parse_headers(self, param):
        regex = re.search(r"headers: ?(.+?) ?,", param)
        if regex and regex.group(1):
            return regex.group(1)
        return UNDEFINED

    def parse_params(self, param):
        regex = re.search(r"formParams: ?(.+?) ?,", param)
        if regex and regex.group(1):
            return regex.group(1)
        return ""

    def parse_response(self, param):
        regex = re.search(r"Response: ?(.+)$", param)
        if regex and regex.group(1):
            return self.escape_for_json(regex.group(1))
        return None
