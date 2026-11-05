"""Export the D1 database to a private gzip file on the VPS."""
import gzip
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/cloud-midterm-d1')
BACKUPS = ROOT / 'backups'
ACCOUNT = 'c6ababb4c45c2abec4bf14b84340a2d4'
DATABASE = 'eb4b1d10-e6c2-4b83-a861-0fb04bb1747d'
TOKEN = (ROOT / 'secrets/cf-api-token').read_text().strip()
URL = f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/d1/database/{DATABASE}/export'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirect())


def post(body):
    request = urllib.request.Request(URL, data=json.dumps(body).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    with opener.open(request, timeout=30) as response:
        data = json.load(response)
    if not data.get('success'):
        raise RuntimeError('D1 export request was rejected')
    return data['result']


def main():
    os.umask(0o077)
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    if shutil.disk_usage(BACKUPS).free < 1024**3:
        raise RuntimeError('Insufficient free disk space for backup')
    state = post({'output_format': 'polling'})
    deadline = time.monotonic() + 180
    while state.get('status') != 'complete':
        if state.get('status') == 'error' or not state.get('at_bookmark'):
            raise RuntimeError('D1 export did not start')
        if time.monotonic() > deadline:
            raise TimeoutError('D1 export timed out')
        time.sleep(2)
        state = post({'output_format': 'polling', 'current_bookmark': state['at_bookmark']})
    download = state['result']['signed_url']
    if not download.startswith('https://'):
        raise RuntimeError('Export URL is not HTTPS')
    destination = BACKUPS / ('d1-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.sql.gz')
    if destination.exists():
        raise FileExistsError('Backup name already exists')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.d1-', suffix='.tmp', dir=BACKUPS, delete=False) as raw:
            temporary = Path(raw.name)
            with urllib.request.urlopen(download, timeout=60) as source, gzip.GzipFile(fileobj=raw, mode='wb') as output:
                shutil.copyfileobj(source, output)
            raw.flush()
            os.fsync(raw.fileno())
        with gzip.open(temporary, 'rb') as exported:
            if not exported.read(1):
                raise RuntimeError('D1 export is empty')
        os.replace(temporary, destination)
        temporary = None
        print('D1 export saved:', destination.name)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


try:
    main()
except Exception as error:
    print('D1 export failed:', type(error).__name__, file=sys.stderr)
    sys.exit(1)
