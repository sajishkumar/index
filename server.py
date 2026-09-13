#!/usr/bin/env python3
"""
WhatsApp Server with Read Receipts (/read endpoint)
"""

import json
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8080
DATA_FILE = os.path.join(os.path.dirname(__file__), 'messages.json')

message_store = {}
store_lock = threading.Lock()

def load_data():
    global message_store
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                message_store = json.load(f)
    except Exception:
        message_store = {}

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(message_store, f)
    except Exception:
        pass

load_data()

HTML_FILE = os.path.join(os.path.dirname(__file__), 'chat.html')

class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_cors_headers(self, code=200, content_type='application/json'):
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Content-Type', content_type)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_cors_headers(200)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in ('/', '/chat.html', '/index.html'):
            try:
                with open(HTML_FILE, 'rb') as f:
                    content = f.read()
                self.send_cors_headers(200, 'text/html; charset=utf-8')
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, str(e))
            return

        if path == '/messages':
            room = params.get('room', ['default'])[0]
            since = float(params.get('since', ['0'])[0])

            with store_lock:
                msgs = message_store.get(room, [])
                new_msgs = [m for m in msgs if m.get('ts', 0) > since]

            self.send_cors_headers(200, 'application/json')
            self.wfile.write(json.dumps(new_msgs).encode('utf-8'))
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/send':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                room = data.get('room', 'default')
                data['ts'] = time.time()
                data['readBy'] = [data.get('uid')] # Sender has read their own message

                with store_lock:
                    if room not in message_store:
                        message_store[room] = []
                    message_store[room].append(data)
                    if len(message_store[room]) > 1000:
                        message_store[room] = message_store[room][-1000:]
                    save_data()

                self.send_cors_headers(200, 'application/json')
                self.wfile.write(json.dumps({'ok': True, 'ts': data['ts']}).encode('utf-8'))
            except Exception as e:
                self.send_cors_headers(400, 'application/json')
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return

        # Mark messages as READ: POST /read
        if path == '/read':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                room = data.get('room', 'default')
                uid = data.get('uid')
                read_ids = set(data.get('readIds', []))

                with store_lock:
                    updated = False
                    if room in message_store:
                        for m in message_store[room]:
                            if m.get('id') in read_ids:
                                if 'readBy' not in m:
                                    m['readBy'] = [m.get('uid')]
                                if uid and uid not in m['readBy']:
                                    m['readBy'].append(uid)
                                    updated = True
                    if updated:
                        save_data()

                self.send_cors_headers(200, 'application/json')
                self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
            except Exception as e:
                self.send_cors_headers(400, 'application/json')
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return

        if path == '/clear':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                room = data.get('room', 'default')
                with store_lock:
                    message_store[room] = []
                    save_data()
                self.send_cors_headers(200, 'application/json')
                self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
            except Exception as e:
                self.send_cors_headers(400, 'application/json')
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return

        self.send_error(404)

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), ChatHandler)
    print(f'WhatsApp Server with Read Receipts running on http://0.0.0.0:{PORT}')
    server.serve_forever()
