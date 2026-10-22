"""Local-only JSON API for the Stockroom demo."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from .store import Stockroom


class Handler(BaseHTTPRequestHandler):
    store = None
    def send_json(self, status, data):
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def read_json(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>65536: raise ValueError('Request body exceeds 64 KB.')
        if not length: raise ValueError('A JSON request body is required.')
        try: return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError,UnicodeDecodeError): raise ValueError('Request body must be valid JSON.')
    def do_GET(self):
        url=urlparse(self.path)
        try:
            if url.path=='/api/health': return self.send_json(200,{'status':'ok','service':'stockroom'})
            if url.path=='/api/products': return self.send_json(200,{'items':self.store.list_products(parse_qs(url.query).get('q',[''])[0])})
            if url.path=='/api/movements': return self.send_json(200,{'items':self.store.movements(int(parse_qs(url.query).get('limit',['50'])[0]))})
            if url.path=='/api/reports/stock': return self.send_json(200,self.store.report())
            return self.send_json(404,{'error':'Route not found.'})
        except (ValueError,LookupError) as exc: return self.send_json(400,{'error':str(exc)})
        except Exception: return self.send_json(500,{'error':'Unexpected server error.'})
    def do_POST(self):
        route=urlparse(self.path).path
        try:
            body=self.read_json()
            if not isinstance(body,dict): raise ValueError('JSON body must be an object.')
            if route=='/api/products':
                try: result=self.store.create_product(body.get('sku'),body.get('name'),body.get('unit_price_cents'),body.get('reorder_level',5))
                except Exception as exc:
                    if 'UNIQUE constraint failed' in str(exc): return self.send_json(409,{'error':'SKU already exists.'})
                    raise
                return self.send_json(201,result)
            if route=='/api/stock': return self.send_json(201,self.store.receive(body.get('sku'),body.get('quantity'),body.get('reference')))
            if route=='/api/sales': return self.send_json(201,self.store.sell(body.get('items'),body.get('idempotency_key')))
            return self.send_json(404,{'error':'Route not found.'})
        except ArithmeticError as exc: return self.send_json(409,{'error':str(exc)})
        except LookupError as exc: return self.send_json(404,{'error':str(exc)})
        except ValueError as exc: return self.send_json(400,{'error':str(exc)})
        except Exception: return self.send_json(500,{'error':'Unexpected server error.'})
    def log_message(self, fmt, *args): pass


def serve(host='127.0.0.1',port=8060,database='stockroom.sqlite3'):
    Handler.store=Stockroom(database)
    httpd=ThreadingHTTPServer((host,port),Handler)
    print(f'Stockroom running at http://{host}:{port} (SQLite: {Path(database).resolve()})')
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: httpd.server_close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8060);p.add_argument('--database',default=os.environ.get('STOCKROOM_DB','stockroom.sqlite3'))
    a=p.parse_args();serve(a.host,a.port,a.database)
