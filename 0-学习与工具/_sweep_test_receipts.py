"""Synthetic HTTP transport for tests; exercise the production receipt parser."""
import json
from unittest.mock import patch

def receipt_sender(module, errcode=0):
    production_send = module._send_wecom_markdown
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({'errcode': errcode, 'req_id': 'synthetic-test-only'}).encode('utf8')
    def send(url, text):
        with patch.object(module.urllib.request, 'urlopen', return_value=Response()):
            return production_send(url, text)
    return send
