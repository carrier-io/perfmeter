from os import environ
import requests
from traceback import format_exc
import json

URL = environ.get('galloper_url')
ADDITIONAL_FILES = environ.get("additional_files")

if not all(a for a in [URL, ADDITIONAL_FILES]):
    exit(0)

try:
    files = json.loads(ADDITIONAL_FILES)
    for file, path in files.items():
        r = requests.get(f'{URL}/artifacts/{file}', allow_redirects=True)
        with open(path, 'wb') as file_data:
            file_data.write(r.content)
except Exception:
    print(format_exc())

