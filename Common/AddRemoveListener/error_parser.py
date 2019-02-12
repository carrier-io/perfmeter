from time import time
import warnings
import contextlib
import traceback
import sys
import requests
from reportportal_client import ReportPortalServiceAsync
from influxdb import InfluxDBClient
from functools import partial
import yaml
from jira import JIRA
import re
import hashlib


PATH_TO_CONFIG = "/tmp/config.yaml"


class partialmethod(partial):
    def __get__(self, instance, owner):
        if instance is None:
            return self

        return partial(self.func, instance, *(self.args or ()),
                       **(self.keywords or {}))


class TestResultsParser(object):
    def __init__(self, arguments):
        self.args = arguments

    def parse_results(self):
        """Parse test results and send to comparison database"""
        simulation = self.args['test_name']
        errors = {}
        unparsed_counter = 0
        raws = dict()
        try:
            client = InfluxDBClient(self.args["influx.host"], self.args["influx.port"], username='', password='',
                                    database=self.args["influx.db"])
            raws = client.query("SELECT * FROM errorMessage WHERE simulation=\'" + simulation +
                                "\' and time >= " + str(self.args['start_time']) + "ms and time <= "
                                + str(self.args['end_time']) + "ms")
            client.close()
        except:
            print("Unable to get data from InfluxDB. Please check connection to " + self.args["influx.host"])
        for error in list(raws.get_points()):
            try:
                count = 1
                key = "%s_%s_%s_%s" % (error['requestName'], error['method'], error['responseCode'], error['errorMessage'])
                if key not in errors:
                    errors[key] = {"Request name": error['requestName'], "Method": error['method'], 'Error count': count,
                                   'Environment': error['envType'], "Response code": error['responseCode'],
                                   "Error message": error['errorMessage'], "Request URL": error['url'],
                                   "Request params": error['params'], "Request headers": error['requestHeaders'],
                                   "Response body": error['responseBody']}
                else:
                    errors[key]['Error count'] += 1
            except:
                unparsed_counter += 1
        if unparsed_counter > 0:
            print("Unparsed errors: %d" % unparsed_counter)
        return errors


class ReportPortal:
    def __init__(self, errors_data, arguments, rp_url, rp_token, rp_project):
        self.errors = errors_data
        self.args = arguments
        self.rp_url = rp_url
        self.rp_token = rp_token
        self.rp_project = rp_project

    @contextlib.contextmanager
    def no_ssl_verification(self):
        old_request = requests.Session.request
        requests.Session.request = partialmethod(old_request, verify=False)

        warnings.filterwarnings('ignore', 'Unverified HTTPS request')
        yield
        warnings.resetwarnings()

        requests.Session.request = old_request

    def timestamp(self):
        return str(int(time() * 1000))

    def create_project(self):
        headers = {'authorization': 'bearer ' + self.rp_token}
        post_data = {'entryType': 'INTERNAL', 'projectName': self.rp_project}
        r = requests.get(self.rp_url + '/' + self.rp_project, headers=headers)
        if r.status_code == 404 or r.text.find(self.rp_project) == -1:
            p = requests.post(self.rp_url, json=post_data, headers=headers)

    def my_error_handler(self, exc_info):
        """
        This callback function will be called by async service client when error occurs.
        Return True if error is not critical and you want to continue work.
        :param exc_info: result of sys.exc_info() -> (type, value, traceback)
        :return:
        """
        print("Error occurred: {}".format(exc_info[1]))
        traceback.print_exception(*exc_info)

    def log_message(self, service, message, errors, level='WARN'):
        if errors[message] is not 'undefined':
            if isinstance(errors[message], list):
                if len(errors[message]) > 1:
                    log = ''
                    for i, error in enumerate(errors[message]):
                        log += message + ' ' + str(i + 1) + ': ' + error + ';;\n'
                    service.log(time=self.timestamp(),
                                message="{}".format(html_decode(log)),
                                level="{}".format(level))
                elif not str(errors[message])[2:-2].__contains__('undefined'):
                    service.log(time=self.timestamp(),
                                message="{}: {}".format(message, html_decode(str(errors[message])[2:-2])),
                                level="{}".format(level))
            else:
                service.log(time=self.timestamp(),
                            message="{}: {}".format(message, html_decode(str(errors[message]))),
                            level="{}".format(level))

    def log_unique_error_id(self, service, request_name, method, response_code):
        error_id = method + '_' + request_name + "_" + response_code
        service.log(time=self.timestamp(), message=error_id, level='ERROR')

    def get_item_name(self, entry):
        if entry['Method'] is not 'undefined' and entry['Response code'] is not 'undefined':
            return "{} {} {}".format(str(entry['Request name']),
                                     str(entry['Method']),
                                     str(entry['Response code']))
        else:
            return str(entry['Request name'])

    def report_errors(self):
        with self.no_ssl_verification():
            self.create_project()
            service = ReportPortalServiceAsync(endpoint=self.rp_url, project=self.rp_project,
                                               token=self.rp_token, error_handler=self.my_error_handler)

            errors = self.errors
            errors_len = len(errors)
            if errors_len > 0:
                # Start launch.
                service.start_launch(name=self.args['test_name'],
                                     start_time=self.timestamp(),
                                     description='This simulation has {} fails'.format(errors_len))
                for key in errors:
                    # Start test item.
                    item_name = "{} {} {}".format(str(errors[key]['Request name']),
                                                  str(errors[key]['Method']),
                                                  str(errors[key]['Response code']))
                    service.start_test_item(name=item_name,
                                            description="This request was failed {} times".format(
                                                errors[key]['Error count']),
                                            tags=[self.args['test_name'], errors[key]['Request name'], 'jmeter_test'],
                                            start_time=self.timestamp(),
                                            item_type="STEP",
                                            parameters={"simulation": self.args['test_name'],
                                                        'duration': int(self.args['end_time'])/1000
                                                        - int(self.args['start_time'])/1000})

                    self.log_message(service, 'Request name', errors[key], 'WARN')
                    self.log_message(service, 'Method', errors[key], 'WARN')
                    self.log_message(service, 'Request URL', errors[key], 'WARN')
                    self.log_message(service, 'Request params', errors[key], 'WARN')
                    self.log_message(service, 'Request headers', errors[key], 'INFO')
                    self.log_message(service, 'Environment', errors[key], 'INFO')
                    self.log_message(service, 'Error count', errors[key], 'WARN')
                    self.log_message(service, 'Error message', errors[key], 'WARN')
                    self.log_message(service, 'Response code', errors[key], 'WARN')
                    self.log_message(service, 'Response body', errors[key], 'WARN')
                    self.log_unique_error_id(service, errors[key]['Request name'], errors[key]['Method'],
                                             errors[key]['Response code'])

                    service.finish_test_item(end_time=self.timestamp(), status="FAILED")
            else:
                service.start_launch(name=self.args['test_name'],
                                     start_time=self.timestamp(),
                                     description='This simulation has no fails')

            # Finish launch.
            service.finish_launch(end_time=self.timestamp())

            service.terminate()


class JiraWrapper:
    JIRA_REQUEST = 'project={} AND labels in ({})'

    def __init__(self, url, user, password, jira_project, assignee, issue_type='Bug', labels=None, watchers=None,
                 jira_epic_key=None):
        self.valid = True
        self.url = url
        self.password = password
        self.user = user
        try:
            self.connect()
        except:
            self.valid = False
            return
        self.projects = [project.key for project in self.client.projects()]
        self.project = jira_project
        if self.project not in self.projects:
            self.client.close()
            self.valid = False
            return
        self.assignee = assignee
        self.issue_type = issue_type
        self.labels = list()
        if labels:
            self.labels = [label.strip() for label in labels.split(",")]
        self.watchers = list()
        if watchers:
            self.watchers = [watcher.strip() for watcher in watchers.split(",")]
        self.jira_epic_key = jira_epic_key
        self.client.close()

    def connect(self):
        self.client = JIRA(self.url, basic_auth=(self.user, self.password))

    def markdown_to_jira_markdown(self, content):
        return content.replace("###", "h3.").replace("**", "*")

    def create_issue(self, title, priority, description, issue_hash, attachments=None, get_or_create=True,
                     additional_labels=None):
        description = self.markdown_to_jira_markdown(description)
        _labels = [issue_hash]
        if additional_labels and isinstance(additional_labels, list):
            _labels.extend(additional_labels)
        _labels.extend(self.labels)
        issue_data = {
            'project': {'key': self.project},
            'summary': re.sub('[^A-Za-z0-9//\. _]+', '', title),
            'description': description,
            'issuetype': {'name': self.issue_type},
            'assignee': {'name': self.assignee},
            'priority': {'name': priority},
            'labels': _labels
        }
        jira_request = self.JIRA_REQUEST.format(issue_data["project"]["key"], issue_hash)
        if get_or_create:
            issue, created = self.get_or_create_issue(jira_request, issue_data)
        else:
            issue = self.post_issue(issue_data)
            created = True
        if attachments:
            for attachment in attachments:
                if 'binary_content' in attachment:
                    self.add_attachment(issue.key,
                                        attachment=attachment['binary_content'],
                                        filename=attachment['message'])
        for watcher in self.watchers:
            self.client.add_watcher(issue.id, watcher)
        if self.jira_epic_key:
            self.client.add_issues_to_epic(self.jira_epic_key, [issue.id])
        return issue, created

    def add_attachment(self, issue_key, attachment, filename=None):
        issue = self.client.issue(issue_key)
        for _ in issue.fields.attachment:
            if _.filename == filename:
                return
        self.client.add_attachment(issue, attachment, filename)

    def post_issue(self, issue_data):
        print(issue_data)
        issue = self.client.create_issue(fields=issue_data)
        return issue

    def get_or_create_issue(self, search_string, issue_data):
        issuetype = issue_data['issuetype']['name']
        created = False
        jira_results = self.client.search_issues(search_string)
        issues = []
        for each in jira_results:
            if each.fields.summary == issue_data.get('summary', None):
                issues.append(each)
        if len(issues) == 1:
            issue = issues[0]
            print(issuetype + 'issue already exists:' + issue.key)
        else:
            issue = self.post_issue(issue_data)
            created = True
        return issue, created


def create_description(error, arguments):
    description = ""
    if arguments['test_name']:
        description += "*Simulation*: " + arguments['test_name'] + "\n"
    if error['Request URL']:
        description += "*Request URL*: " + error['Request URL'] + "\n"
    if error['Request headers']:
        description += "*Request headers*: " + error['Request headers'] + "\n"
    if error['Request params']:
        description += "*Request params*: " + html_decode(str(error['Request params'])).replace("&", "\n") + "\n"
    if error['Error message']:
        description += "*Error message*: " + str(error['Error message']) + "\n"
    if error['Error count']:
        description += "*Error count*: " + str(error['Error count']) + "\n"
    if error['Response code']:
        description += "*Response code*: " + error['Response code'] + "\n"
    if error['Response body']:
        description += "*Response body*: " + str(error['Response body']).replace("\n", "") + "\n"
    return description


def html_decode(s):
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
        ('\\"', '"'),
        ('[', '%5B'),
        (']', '%5D'),
        ('?', '%3F'),
        ('{', '%7B'),
        ('}', '%7D'),
        ('$', '%24'),
        ('@', '%40'),
        ('"', '%22'),
        ('=', '%3D'),
        ('+', '%2B')
    )
    for code in html_codes:
        s = s.replace(code[1], code[0])
    return s


def finding_error_string(error, arguments):
    error_str = arguments['test_name'] + "_" + str(error['Request URL']) + "_" + str(error['Error message']) + "_" \
                    + error['Request name'] + "3"
    return error_str


def get_hash_code(error, arguments):
    hash_string = finding_error_string(error, arguments).strip()
    return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()


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
        print("InfluxDB is not configured. Exit")
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


def report_errors(errors, args):
    report_types = []
    with open(PATH_TO_CONFIG, "rb") as f:
        config = yaml.load(f.read())
    if config:
        report_types = list(config.keys())

    rp_service = None
    if report_types.__contains__('reportportal'):
        rp_project = config['reportportal'].get("rp_project_name")
        rp_url = config['reportportal'].get("rp_host")
        rp_token = config['reportportal'].get("rp_token")
        if not (rp_project and rp_url and rp_token):
            print("ReportPortal configuration values missing, proceeding without report portal integration")
        else:
            rp_service = ReportPortal(errors, args, rp_url, rp_token, rp_project)
    if rp_service:
        rp_service.my_error_handler(sys.exc_info())
        rp_service.report_errors()

    jira_service = None
    if report_types.__contains__('jira'):
        jira_url = config['jira'].get("url", None)
        jira_user = config['jira'].get("username", None)
        jira_pwd = config['jira'].get("password", None)
        jira_project = config['jira'].get("jira_project", None)
        jira_assignee = config['jira'].get("assignee", None)
        jira_issue_type = config['jira'].get("issue_type", 'Bug')
        jira_lables = config['jira'].get("labels", '')
        jira_watchers = config['jira'].get("watchers", '')
        jira_epic_key = config['jira'].get("epic_link", None)
        if not (jira_url and jira_user and jira_pwd and jira_project and jira_assignee):
            print("Jira integration configuration is messed up, proceeding without Jira")
        else:
            jira_service = JiraWrapper(jira_url, jira_user, jira_pwd, jira_project,
                                       jira_assignee, jira_issue_type, jira_lables,
                                       jira_watchers, jira_epic_key)
    if jira_service:
        jira_service.connect()
        if jira_service.valid:
            for error in errors:
                issue_hash = get_hash_code(errors[error], args)
                description = create_description(errors[error], args)
                jira_service.create_issue(errors[error]['Request name'], 'Major', description, issue_hash)
        else:
            print("Failed connection to Jira or project does not exist")


if __name__ == '__main__':
    args = parse_args(sys.argv[1])
    testResultsParser = TestResultsParser(args)
    errors = testResultsParser.parse_results()
    report_errors(errors, args)
