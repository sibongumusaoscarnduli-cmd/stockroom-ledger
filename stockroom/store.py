"""SQLite inventory and sales domain. All money is stored in integer cents."""
from contextlib import contextmanager
from datetime import datetime, timezone
import re
import sqlite3
import hashlib
import json

SKU_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$')

SCHEMA = '''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY,
 sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
 name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
 quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
 reorder_level INTEGER NOT NULL DEFAULT 5 CHECK(reorder_level >= 0),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movements (
 id INTEGER PRIMARY KEY,
 product_id INTEGER NOT NULL REFERENCES products(id),
 kind TEXT NOT NULL CHECK(kind IN ('receipt','sale')),
 quantity_delta INTEGER NOT NULL CHECK(quantity_delta != 0),
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
 reference TEXT NOT NULL,
 request_key TEXT UNIQUE,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS movements_product_time ON movements(product_id, id DESC);
CREATE TABLE IF NOT EXISTS sales (request_key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
'''


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def validate_sku(sku):
    if not isinstance(sku, str):
        raise ValueError('SKU must be 1–40 letters, digits, dots, underscores or hyphens.')
    sku = sku.strip()
    if not SKU_RE.fullmatch(sku):
        raise ValueError('SKU must be 1–40 letters, digits, dots, underscores or hyphens.')
    return sku


def validate_quantity(value, label='quantity'):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 1_000_000:
        raise ValueError(f'{label} must be a whole number between 1 and 1,000,000.')
    return value


class Stockroom:
    def __init__(self, path='stockroom.sqlite3'):
        self.path = str(path)
        with self.connect() as db:
            db.executescript(SCHEMA)
            columns={row['name'] for row in db.execute('PRAGMA table_info(sales)')}
            if 'result_json' not in columns:
                db.execute("ALTER TABLE sales ADD COLUMN result_json TEXT NOT NULL DEFAULT '{}'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('PRAGMA busy_timeout = 5000')
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def product(row):
        if row is None:
            return None
        d = dict(row)
        d['unit_price'] = f"{d.pop('unit_price_cents') / 100:.2f}"
        return d

    def create_product(self, sku, name, unit_price_cents, reorder_level=5):
        sku = validate_sku(sku)
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValueError('Product name must contain 1–120 characters.')
        if isinstance(unit_price_cents, bool) or not isinstance(unit_price_cents, int) or not 0 <= unit_price_cents <= 100_000_000_000:
            raise ValueError('unit_price_cents must be an integer from 0 to 100,000,000,000.')
        if isinstance(reorder_level, bool) or not isinstance(reorder_level, int) or not 0 <= reorder_level <= 1_000_000:
            raise ValueError('reorder_level must be a whole number from 0 to 1,000,000.')
        with self.transaction() as db:
            cur = db.execute('INSERT INTO products(sku,name,unit_price_cents,reorder_level,created_at) VALUES(?,?,?,?,?)',
                             (sku, name.strip(), unit_price_cents, reorder_level, now()))
            return self.product(db.execute('SELECT * FROM products WHERE id=?', (cur.lastrowid,)).fetchone())

    def list_products(self, query=''):
        query = query.strip()
        with self.connect() as db:
            if query:
                rows = db.execute("SELECT * FROM products WHERE sku LIKE ? OR name LIKE ? ORDER BY name COLLATE NOCASE, id", (f'%{query}%', f'%{query}%'))
            else:
                rows = db.execute('SELECT * FROM products ORDER BY name COLLATE NOCASE, id')
            return [self.product(row) for row in rows]

    def receive(self, sku, quantity, reference):
        sku = validate_sku(sku); quantity = validate_quantity(quantity)
        if not isinstance(reference, str) or not reference.strip() or len(reference.strip()) > 100:
            raise ValueError('reference must contain 1–100 characters.')
        with self.transaction() as db:
            p = db.execute('SELECT * FROM products WHERE sku=? COLLATE NOCASE', (sku,)).fetchone()
            if p is None: raise LookupError('Product SKU was not found.')
            db.execute('UPDATE products SET quantity=quantity+? WHERE id=?', (quantity, p['id']))
            db.execute("INSERT INTO movements(product_id,kind,quantity_delta,unit_price_cents,reference,created_at) VALUES(?,'receipt',?,?,?,?)",
                       (p['id'], quantity, p['unit_price_cents'], reference.strip(), now()))
            return self.product(db.execute('SELECT * FROM products WHERE id=?', (p['id'],)).fetchone())

    def sell(self, items, request_key):
        if not isinstance(items, list) or not items or len(items) > 100:
            raise ValueError('items must contain between 1 and 100 product lines.')
        if not isinstance(request_key, str) or not request_key.strip() or len(request_key.strip()) > 100:
            raise ValueError('idempotency_key must contain 1–100 characters.')
        clean=[]
        for line in items:
            if not isinstance(line, dict): raise ValueError('Each item must be an object.')
            clean.append((validate_sku(line.get('sku')), validate_quantity(line.get('quantity'))))
        if len({sku.casefold() for sku,_ in clean}) != len(clean):
            raise ValueError('A sale may contain each SKU only once.')
        key=request_key.strip()
        with self.transaction() as db:
            payload_hash=hashlib.sha256(json.dumps(clean,separators=(',',':')).encode()).hexdigest()
            prior=db.execute('SELECT payload_hash,result_json FROM sales WHERE request_key=?', (key,)).fetchone()
            if prior:
                if prior['payload_hash'] != payload_hash: raise ValueError('Idempotency key was already used with a different sale.')
                result=json.loads(prior['result_json'])
                if not result:
                    result={'request_key':key,'items':[self.product(db.execute('SELECT * FROM products WHERE sku=? COLLATE NOCASE',(sku,)).fetchone()) for sku,_ in clean]}
                result['replayed']=True
                return result
            products=[]
            for sku,qty in clean:
                p=db.execute('SELECT * FROM products WHERE sku=? COLLATE NOCASE',(sku,)).fetchone()
                if p is None: raise LookupError(f'Product SKU {sku} was not found.')
                if p['quantity'] < qty: raise ArithmeticError(f"Insufficient stock for {p['sku']}: {p['quantity']} available, {qty} requested.")
                products.append((p,qty))
            db.execute('INSERT INTO sales(request_key,payload_hash,created_at) VALUES(?,?,?)',(key,payload_hash,now()))
            for p,qty in products:
                db.execute('UPDATE products SET quantity=quantity-? WHERE id=?',(qty,p['id']))
                db.execute("INSERT INTO movements(product_id,kind,quantity_delta,unit_price_cents,reference,request_key,created_at) VALUES(?,'sale',?,?,?, ?,?)",
                           (p['id'],-qty,p['unit_price_cents'],key,key,now()))
            result={'request_key':key,'replayed':False,'items':[self.product(db.execute('SELECT * FROM products WHERE id=?',(p['id'],)).fetchone()) for p,_ in products]}
            db.execute('UPDATE sales SET result_json=? WHERE request_key=?',(json.dumps(result,separators=(',',':')),key))
            return result

    def movements(self, limit=50):
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=200: raise ValueError('limit must be from 1 to 200.')
        with self.connect() as db:
            rows=db.execute('SELECT m.id,p.sku,p.name,m.kind,m.quantity_delta,m.unit_price_cents,m.reference,m.request_key,m.created_at FROM movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT ?', (limit,))
            result=[]
            for row in rows:
                d=dict(row);d['unit_price']=f"{d.pop('unit_price_cents')/100:.2f}";result.append(d)
            return result

    def report(self):
        with self.connect() as db:
            low=[self.product(r) for r in db.execute('SELECT * FROM products WHERE quantity<=reorder_level ORDER BY quantity,sku')]
            totals=db.execute('SELECT COUNT(*) AS products, COALESCE(SUM(quantity),0) AS units, COALESCE(SUM(quantity*unit_price_cents),0) AS stock_value_cents FROM products').fetchone()
            return {**dict(totals),'stock_value':f"{totals['stock_value_cents']/100:.2f}",'low_stock':low}
