"""Expose only this application's D1 query endpoint over a local Unix socket."""
import http.server
import json
import os
import socketserver
import urllib.error
import urllib.request
from pathlib import Path

SOCKET = Path('/run/d1/d1.sock')
URL = ('https://api.cloudflare.com/client/v4/accounts/' + os.environ['D1_ACCOUNT_ID']
       + '/d1/database/' + os.environ['D1_DATABASE_ID'] + '/query')
TOKEN = Path('/run/secrets/d1_token').read_text().strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, _format, *args):
        pass

    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if self.path != '/query' or not 1 <= size <= 16384:
                raise ValueError('Invalid request')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or set(payload) != {'sql', 'params'} or not isinstance(payload['sql'], str) or not isinstance(payload['params'], list):
                raise ValueError('Invalid query')
            request = urllib.request.Request(URL, data=json.dumps(payload).encode(), method='POST',
                headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
            with OPENER.open(request, timeout=10) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('Response too large')
            self.send_response(200)
        except (ValueError, OSError, urllib.error.URLError):
            data = b'{"success":false}'
            self.send_response(502)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


if SOCKET.exists():
    SOCKET.unlink()
os.umask(0o117)
with Server(str(SOCKET), Handler) as server:
    server.serve_forever()
