# init_db.py
import sqlite3
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'marketplace.db')
PRODUCTS_JSON = os.path.join(BASE, 'products.json')

schema = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL -- NOTE: plaintext for demo only (replace with hash in prod)
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    created_at TEXT,
    total REAL,
    shipping TEXT,  
    payment TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    product_id TEXT,
    quantity INTEGER,
    price REAL,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
"""

def main():
    if os.path.exists(DB):
        print("WARNING: marketplace.db exists. It will be reused. Remove it to reinitialize.")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.executescript(schema)
    conn.commit()

    # Load products.json and insert if not exists
    with open(PRODUCTS_JSON, 'r', encoding='utf-8') as f:
        products = json.load(f)
    inserted = 0
    for p in products:
        cur.execute("SELECT 1 FROM products WHERE id = ?", (p['id'],))
        if cur.fetchone():
            continue
        cur.execute("INSERT INTO products (id, name, description, price, stock) VALUES (?, ?, ?, ?, ?)",
                    (p['id'], p['name'], p.get('description',''), p['price'], p['stock']))
        inserted += 1
    conn.commit()
    print(f"DB initialized. Products inserted: {inserted}")
    conn.close()

if __name__ == '__main__':
    main()