import os
import sqlite3
import barcode
from barcode.writer import ImageWriter
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)
DB_NAME = "inventario.db"
BARCODE_FOLDER = os.path.join("static", "barcodes")
os.makedirs(BARCODE_FOLDER, exist_ok = True)

def get_db():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection
    
def init_db():
    with get_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS productos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre_producto TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.commit()
init_db()

@app.route("/")
def index():
    with get_db() as connection:
        productos = connection.execute("SELECT * FROM productos ORDER BY id DESC").fetchall()
    return render_template("index.html", productos=productos)

@app.route("/api/crear", methods=["POST"])
def crear_producto():
    nombre = request.form.get("nombre", "").strip()
    stock = int(request.form.get("stock", 0))
    codigo = request.form.get("codigo", "").strip()
    
    with get_db() as connection:
        if not codigo:
            cursor = connection.execute("SELECT MAX(id) FROM productos")
            max_id = cursor.fetchone()[0] or 0
            codigo = f"INT{max_id + 1:05d}"
            
            Code128 = barcode.get_barcode_class("code128")
            barcode_instance = Code128(codigo, writer=ImageWriter())
            barcode_path = os.path.join(BARCODE_FOLDER, codigo)
            barcode_instance.save(barcode_path)
            
        try:
            connection.execute(
                "INSERT INTO productos(codigo, nombre_producto, stock) VALUES (?, ?, ?)", (codigo, nombre, stock)
            )
            connection.commit()
        except sqlite3.IntegrityError:
            return jsonify({"status": "error", "mensaje": "El codigo ya existe."}), 400
            
    return redirect(url_for("index"))

@app.route("/api/sumar", methods=["POST"])
def sumar_stock():
    data = request.get_json() or {}
    codigo = data.get("codigo", "").strip()
    cantidad = int(data.get("cantidad", 1))
    
    if not codigo:
        return jsonify({"status": "error", "mensaje": "Codigo Invalido."}), 400
    
    with get_db() as connection:
        productos = connection.execute(
            "SELECT * FROM productos WHERE codigo = ?", (codigo,)
        ).fetchone()
        
        if not productos:
            return jsonify({"status": "not found", "mensaje": "Producto no encontrado"}), 404
        
        nuevo_stock = productos["stock"] + cantidad
        connection.execute(
            "UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, productos["id"])
        )
        connection.commit()
        
        return jsonify({
            "status": "listo",
            "codigo": codigo,
            "stock": nuevo_stock,
            "mensaje": f"+{cantidad} a {productos['nombre_producto']} (Total: {nuevo_stock})"
        })
@app.route("/api/eliminar", methods=["POST"])
def eliminarProducto():
    data = request.get_json() or {}
    codigo = data.get("codigo", "").strip()
    
    with get_db() as connection:
        connection.execute("DELETE FROM productos WHERE codigo = ?", (codigo,))
        connection.commit()
    img_path = os.path.join(BARCODE_FOLDER, f"{codigo}.png")
    if os.path.exists(img_path):
        os.remove(img_path)
        
    return jsonify({"status": "listo", "codigo": codigo, "mensaje": "Producto eliminado."})
    
@app.route("/api/descontar", methods=["POST"])
def descontar_stock():
    data = request.get_json() or {}
    codigo = data.get("codigo", "").strip()
    
    if not codigo:
        return jsonify({"status": "error", "mensaje": "Codigo vacio."}), 400
        
    with get_db() as connection:
        producto = connection.execute(
            "SELECT * FROM productos WHERE codigo = ?", (codigo,)
        ).fetchone()
        
        if not producto:
            return jsonify({
                "status": "not_found",
                "mensaje": f"No se encontro el producto (Codigo: {codigo})"
            }), 404
            
        if producto["stock"] <= 0:
            return jsonify({
                "status": "sin_stock",
                "nombre": producto["nombre_producto"],
                "stock": 0,
                "mensaje": f"El producto {producto['nombre_producto']} se encuentra fuera de stock"
            })
            
        nuevo_stock = producto["stock"] - 1
        connection.execute(
            "UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, producto["id"])
        )
        connection.commit()
        
        return jsonify({
            "status": "listo",
            "codigo": producto["codigo"],
            "nombre": producto["nombre_producto"],
            "stock": nuevo_stock,
            "mensaje": f"-1 {producto['nombre_producto']} (Quedan: {nuevo_stock})"
        })
if __name__ == "__main__":
    app.run(debug=True, port=5000)
