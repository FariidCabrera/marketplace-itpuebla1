from flask import Flask, request, jsonify, session, send_from_directory, send_file, abort
import sqlite3, threading, os, json, io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'marketplace.db')

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'super-secret-key'
lock = threading.Lock()

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------- CONFIGURACIÓN DE IMÁGENES ---------------------
UPLOAD_FOLDER = os.path.join(BASE, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'png','jpg','jpeg','gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

# ----------------------- SERVIR INDEX ---------------------------------
@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE, "static"), "index.html")

# ----------------------- REGISTRO --------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Usuario y contraseña requeridos"}), 400

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return jsonify({"status": "ok", "message": "Usuario registrado con éxito"})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "El usuario ya existe"}), 409
    finally:
        conn.close()

# ----------------------- LOGIN -----------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()

    if row:
        session["user_id"] = row["id"]
        session["username"] = username
        return jsonify({"status": "ok", "message": "Login correcto", "user": {"id": row["id"], "username": username}})

    return jsonify({"status": "error", "message": "Credenciales incorrectas"}), 401

# ----------------------- LOGOUT ----------------------------------------
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})

# ----------------------- PRODUCTOS -------------------------------------
@app.route("/api/products", methods=["GET"])
def products():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# ----------------------- SUBIR IMAGEN ----------------------------------
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'ok': False, 'message':'No file field named "image"'}), 400
    f = request.files['image']
    if f.filename == '':
        return jsonify({'ok':False, 'message':'No filename'}), 400
    if not allowed_file(f.filename):
        return jsonify({'ok':False, 'message':'Extensión no permitida'}), 400
    
    # Asegurar y luego prefijar con timestamp
    original_filename = secure_filename(f.filename)
    filename = f"{int(time.time())}_{original_filename}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        f.save(path)
        url = f"/static/uploads/{filename}"
        return jsonify({'ok':True, 'url': url})
    except Exception as e:
        return jsonify({'ok':False, 'message':f"Error al guardar: {str(e)}"}), 500

# ----------------------- AGREGAR PRODUCTO ------------------------------
@app.route('/api/add-product', methods=['POST'])
def add_product():
    # Nota: Aquí se asume que 'get_conn()' y 'products' tabla existen y son accesibles.
    # En un entorno real, probablemente agregarías una verificación de autenticación/rol de administrador.
    data = request.json or {}
    name = data.get('name')
    description = data.get('description','')
    
    # Convertir a float y manejar posibles errores de tipo
    try:
        price = float(data.get('price') or 0)
    except ValueError:
        return jsonify({'status':'error','message':'Precio debe ser un número válido'}), 400

    # Convertir a int y manejar posibles errores de tipo
    try:
        stock = int(data.get('stock') or 0)
    except ValueError:
        return jsonify({'status':'error','message':'Stock debe ser un número entero válido'}), 400
        
    image = data.get('image')  # ex: /static/uploads/xxx.jpg

    if not name or price <= 0:
        return jsonify({'status':'error','message':'Nombre y precio (>0) requeridos'}), 400

    conn = get_conn(); cur = conn.cursor()
    with lock: # Usar el lock para asegurar la integridad de la base de datos
        try:
            cur.execute("INSERT INTO products (name, description, price, stock, image) VALUES (?, ?, ?, ?, ?)",
                        (name, description, price, stock, image))
            conn.commit()
            return jsonify({'status':'ok','product_id': cur.lastrowid})
        except Exception as e:
            conn.rollback()
            return jsonify({'status':'error','message':str(e)}), 500
        finally:
            conn.close()

# ----------------------- CARRITO (SESSION) -----------------------------
@app.route("/api/cart", methods=["GET", "POST", "DELETE"])
def cart():
    if "cart" not in session:
        session["cart"] = []

    # obtener carrito
    if request.method == "GET":
        return jsonify(session["cart"])

    # agregar producto
    if request.method == "POST":
        data = request.json or {}
        pid = data.get("productId")
        qty = int(data.get("quantity", 1))

        cart = session["cart"]
        found = False
        for item in cart:
            if item["productId"] == pid:
                item["quantity"] += qty
                found = True
                break

        if not found:
            cart.append({"productId": pid, "quantity": qty})

        session["cart"] = cart
        return jsonify({"status": "ok", "cart": cart})

    # limpiar carrito
    if request.method == "DELETE":
        session["cart"] = []
        return jsonify({"status": "ok"})

# ----------------------- CREAR ORDEN -----------------------------------
@app.route("/api/order", methods=["POST"])
def create_order():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Debes iniciar sesión"}), 401

    data = request.json or {}

    items = data.get("items", [])
    shipping = data.get("shippingAddress", {})
    payment = data.get("payment", {})

    if not items:
        return jsonify({"status": "error", "message": "Carrito vacío"}), 400

    conn = get_conn()
    cur = conn.cursor()

    with lock:
        try:
            total = 0

            # verificar stock
            for item in items:
                cur.execute("SELECT price, stock FROM products WHERE id=?", (item["productId"],))
                product = cur.fetchone()
                if not product:
                    return jsonify({"status": "error", "message": "Producto no encontrado"}), 404

                if product["stock"] < item["quantity"]:
                    return jsonify({"status": "error", "message": "Stock insuficiente"}), 409

                total += product["price"] * item["quantity"]

            # crear orden
            now = datetime.utcnow().isoformat() + "Z"
            cur.execute("INSERT INTO orders (user_id, created_at, total, shipping, payment) VALUES (?, ?, ?, ?, ?)",
                        (session["user_id"], now, total, json.dumps(shipping), json.dumps(payment)))

            order_id = cur.lastrowid

            # descontar stock + insertar items
            for item in items:
                cur.execute("SELECT price FROM products WHERE id=?", (item["productId"],))
                price = cur.fetchone()["price"]

                cur.execute("UPDATE products SET stock = stock - ? WHERE id=?", (item["quantity"], item["productId"]))

                cur.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                            (order_id, item["productId"], item["quantity"], price))

            conn.commit()
            return jsonify({"status": "ok", "order_id": order_id})

        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500

        finally:
            conn.close()

# ----------------------- TICKET PDF ----------------------
@app.route("/api/order/<int:order_id>/ticket")
def ticket(order_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = cur.fetchone()

    if not order:
        return abort(404)

    cur.execute("SELECT product_id, quantity, price FROM order_items WHERE order_id=?", (order_id,))
    items = cur.fetchall()

    conn.close()

    # PDF en memoria
    pdf = io.BytesIO()
    p = canvas.Canvas(pdf, pagesize=letter)
    width, height = letter

    y = height - 40
    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, y, "Ticket de Compra")

    y -= 40
    p.setFont("Helvetica", 12)
    p.drawString(40, y, f"Orden ID: {order['id']}")
    y -= 20
    p.drawString(40, y, f"Total: ${order['total']}")
    y -= 20
    p.drawString(40, y, f"Fecha: {order['created_at']}")
    y -= 30

    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "Items:")
    y -= 20

    p.setFont("Helvetica", 11)
    for it in items:
        p.drawString(40, y, f"- Producto {it['product_id']} x{it['quantity']}  @ ${it['price']}")
        y -= 18

    p.save()
    pdf.seek(0)

    return send_file(pdf, mimetype="application/pdf", download_name=f"ticket_{order_id}.pdf", as_attachment=True)

# ----------------------- INICIAR SERVIDOR -------------------------------
if __name__ == "__main__":
    print("Server running on http://127.0.0.1:5000")
    app.run(debug=True)