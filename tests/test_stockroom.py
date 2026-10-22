import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from stockroom.store import Stockroom
from stockroom.server import Handler


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Stockroom(Path(self.temp.name) / 'test.sqlite3')
        self.store.create_product('BEAN-1', 'Coffee', 8950, 4)
        self.store.create_product('MUG-1', 'Mug', 12000, 4)
        self.store.receive('BEAN-1', 10, 'PO-1')
        self.store.receive('MUG-1', 3, 'PO-2')

    def tearDown(self):
        self.temp.cleanup()

    def test_prices_are_integer_cents_and_displayed_as_decimal(self):
        self.assertEqual(self.store.list_products()[0]['unit_price'], '89.50')

    def test_sku_is_case_insensitive_and_whitespace_is_trimmed(self):
        with self.assertRaises(Exception):
            self.store.create_product(' bean-1 ', 'Duplicate', 100)
        self.assertEqual(self.store.list_products()[0]['sku'], 'BEAN-1')

    def test_invalid_sku_and_quantity_are_rejected(self):
        with self.assertRaises(ValueError): self.store.create_product('bad sku', 'X', 1)
        for quantity in [0, -1, 1.2, True, '2']:
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.store.receive('BEAN-1', quantity, 'PO')

    def test_receipt_updates_quantity_and_creates_ledger_entry(self):
        self.store.receive('BEAN-1', 5, 'PO-3')
        self.assertEqual(self.store.list_products('BEAN-1')[0]['quantity'], 15)
        move = self.store.movements(1)[0]
        self.assertEqual((move['kind'], move['quantity_delta'], move['reference']), ('receipt', 5, 'PO-3'))

    def test_sale_is_atomic_across_multiple_products(self):
        with self.assertRaises(ArithmeticError):
            self.store.sell([{'sku':'BEAN-1','quantity':2},{'sku':'MUG-1','quantity':99}], 'sale-bad')
        items = {p['sku']: p['quantity'] for p in self.store.list_products()}
        self.assertEqual(items, {'BEAN-1': 10, 'MUG-1': 3})
        self.assertFalse(any(m['kind'] == 'sale' for m in self.store.movements()))

    def test_sale_deducts_stock_and_writes_movement(self):
        result = self.store.sell([{'sku':'BEAN-1','quantity':2}], 'sale-1')
        self.assertFalse(result['replayed'])
        self.assertEqual(result['items'][0]['quantity'], 8)
        move = self.store.movements(1)[0]
        self.assertEqual((move['kind'], move['quantity_delta'], move['request_key']), ('sale', -2, 'sale-1'))

    def test_sale_retry_is_idempotent(self):
        first = self.store.sell([{'sku':'BEAN-1','quantity':3}], 'sale-retry')
        retry = self.store.sell([{'sku':'BEAN-1','quantity':3}], 'sale-retry')
        self.assertFalse(first['replayed']); self.assertTrue(retry['replayed'])
        self.assertEqual(retry['items'][0]['quantity'], 7)
        self.assertEqual(len([m for m in self.store.movements() if m['kind']=='sale']), 1)
        self.store.receive('BEAN-1', 5, 'PO-AFTER')
        replay_after_later_change = self.store.sell([{'sku':'BEAN-1','quantity':3}], 'sale-retry')
        self.assertEqual(replay_after_later_change['items'][0]['quantity'], 7)

    def test_idempotency_key_cannot_be_reused_for_different_sale(self):
        self.store.sell([{'sku':'BEAN-1','quantity':1}], 'sale-same')
        with self.assertRaisesRegex(ValueError, 'different sale'):
            self.store.sell([{'sku':'MUG-1','quantity':1}], 'sale-same')

    def test_duplicate_product_lines_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'only once'):
            self.store.sell([{'sku':'BEAN-1','quantity':1},{'sku':'bean-1','quantity':1}], 'sale-lines')

    def test_unknown_sku_is_reported(self):
        with self.assertRaises(LookupError): self.store.receive('UNKNOWN', 1, 'PO')

    def test_low_stock_report_and_inventory_value(self):
        report = self.store.report()
        self.assertEqual(report['products'], 2)
        self.assertEqual(report['units'], 13)
        self.assertEqual(report['stock_value'], '1255.00')
        self.assertEqual([p['sku'] for p in report['low_stock']], ['MUG-1'])

    def test_product_search_filters_catalog(self):
        self.assertEqual([p['sku'] for p in self.store.list_products('coffee')], ['BEAN-1'])


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        Handler.store = Stockroom(Path(cls.temp.name) / 'api.sqlite3')
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.httpd.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); cls.thread.join(); cls.temp.cleanup()

    def call(self, method, path, data=None):
        raw = None if data is None else json.dumps(data).encode()
        req = Request(self.base + path, data=raw, method=method, headers={'Content-Type':'application/json'})
        try:
            with urlopen(req) as res: return res.status, json.loads(res.read())
        except HTTPError as exc: return exc.code, json.loads(exc.read())

    def test_api_health_and_create_stock_sale_report(self):
        self.assertEqual(self.call('GET','/api/health')[0], 200)
        status,p = self.call('POST','/api/products',{'sku':'API-1','name':'Test Item','unit_price_cents':1999,'reorder_level':2})
        self.assertEqual(status,201)
        self.assertEqual(self.call('POST','/api/stock',{'sku':'API-1','quantity':4,'reference':'PO-API'})[0],201)
        self.assertEqual(self.call('POST','/api/sales',{'idempotency_key':'api-sale','items':[{'sku':'API-1','quantity':1}]})[0],201)
        status,report=self.call('GET','/api/reports/stock')
        self.assertEqual((status,report['units'],report['stock_value']), (200,3,'59.97'))

    def test_api_rejects_duplicate_sku_and_insufficient_stock(self):
        self.call('POST','/api/products',{'sku':'DUP','name':'First','unit_price_cents':100})
        self.assertEqual(self.call('POST','/api/products',{'sku':'dup','name':'Second','unit_price_cents':100})[0],409)
        status,body=self.call('POST','/api/sales',{'idempotency_key':'empty-sale','items':[{'sku':'DUP','quantity':1}]})
        self.assertEqual(status,409);self.assertIn('Insufficient stock',body['error'])

    def test_two_concurrent_sales_cannot_sell_the_same_last_unit(self):
        self.call('POST','/api/products',{'sku':'LAST','name':'Last unit','unit_price_cents':100})
        self.call('POST','/api/stock',{'sku':'LAST','quantity':1,'reference':'PO-LAST'})
        barrier=threading.Barrier(3); results=[]
        def sell_one(key):
            barrier.wait()
            results.append(self.call('POST','/api/sales',{'idempotency_key':key,'items':[{'sku':'LAST','quantity':1}]})[0])
        threads=[threading.Thread(target=sell_one,args=(f'last-{i}',)) for i in range(2)]
        for thread in threads:thread.start()
        barrier.wait()
        for thread in threads:thread.join()
        self.assertEqual(sorted(results),[201,409])
        self.assertEqual([p['quantity'] for p in Handler.store.list_products('LAST')],[0])

    def test_api_handles_invalid_json_body(self):
        req=Request(self.base+'/api/products',data=b'{bad',method='POST',headers={'Content-Type':'application/json'})
        try: urlopen(req)
        except HTTPError as exc: self.assertEqual(exc.code,400)
        else: self.fail('Malformed JSON should return HTTP 400')


if __name__ == '__main__': unittest.main()
