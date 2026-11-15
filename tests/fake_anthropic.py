"""Controlled native Messages API fixture. This is not a real model/provider."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextmanager
def native_provider(text='NATIVE_FREELLMAPI_CONTRACT_PASSED'):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'data': [{'id': 'auto'}, {'id': 'example-coder'}]}).encode())

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append({'path': self.path, 'body': data, 'bearer_auth': self.headers.get('Authorization') == 'Bearer test-unified-key',
                             'has_api_key_header': bool(self.headers.get('x-api-key'))})
            if 'count_tokens' in self.path:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"input_tokens":100}')
                return
            result = {'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': data['model'],
                      'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn', 'stop_sequence': None,
                      'usage': {'input_tokens': 100, 'output_tokens': 20}}
            self.send_response(200)
            if data.get('stream'):
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                events = [
                    ('message_start', {'type': 'message_start', 'message': {**result, 'content': [], 'stop_reason': None}}),
                    ('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}}),
                    ('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': text}}),
                    ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                    ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
                                       'usage': {'output_tokens': 20}}),
                    ('message_stop', {'type': 'message_stop'}),
                ]
                for event, body in events:
                    self.wfile.write(('event: ' + event + '\ndata: ' + json.dumps(body) + '\n\n').encode())
                self.wfile.flush()
            else:
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        server.shutdown()
        server.server_close()
