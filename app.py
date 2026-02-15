from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
from conexion import get_connection

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Backend DataFood (Render Postgres) funcionando 🚀"

# =========================
# REGISTER (Postgres)
# =========================
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "")
    email = (data.get("email") or "").strip() or None

    if not username or not password:
        return jsonify({"success": False, "message": "username y password son requeridos"}), 400

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # ✅ Postgres usa %s
        cur.execute("SELECT 1 FROM usuarios WHERE username = %s LIMIT 1;", (username,))
        if cur.fetchone():
            return jsonify({"success": False, "message": "Username ya existe"}), 409

        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        cur.execute(
            "INSERT INTO usuarios (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id_usuario;",
            (username, email, pw_hash)
        )
        new_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({"success": True, "id_usuario": new_id})

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        print("REGISTER ERROR:", e)
        return jsonify({"success": False, "message": "Error registrando usuario"}), 500

    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass


# =========================
# LOGIN (Postgres)
# =========================
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "")

    if not username or not password:
        return jsonify({"success": False, "message": "username y password son requeridos"}), 400

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id_usuario, password_hash FROM usuarios WHERE username = %s LIMIT 1;",
            (username,)
        )
        row = cur.fetchone()

        if not row:
            return jsonify({"success": False, "message": "Credenciales inválidas"}), 401

        id_usuario, pw_hash = row[0], row[1]

        if not bcrypt.checkpw(password.encode("utf-8"), pw_hash.encode("utf-8")):
            return jsonify({"success": False, "message": "Credenciales inválidas"}), 401

        return jsonify({"success": True, "id_usuario": id_usuario}), 200

    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({"success": False, "message": "Error interno en login"}), 500

    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass


# =========================
# MENU (Postgres)
# =========================
@app.route("/menu", methods=["GET"])
def menu():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # PLATOS
        cur.execute("""
            SELECT
                mp.id_menu_platos    AS id,
                mp.nombre_plato      AS nombre,
                mp.precio            AS precio,
                mp.imagen_url        AS "imagenUrl",
                cp.nombre_categoria  AS categoria
            FROM menu_de_platos mp
            INNER JOIN categoria_platos cp
                ON cp.id_categoria_platos = mp.id_categoria_platos
            ORDER BY cp.nombre_categoria, mp.nombre_plato;
        """)
        platos_rows = cur.fetchall()

        platos = [{
            "id": r[0],
            "nombre": r[1],
            "precio": float(r[2]) if r[2] is not None else 0,
            "imagenUrl": r[3],
            "categoria": r[4],
            "tipo": "plato"
        } for r in platos_rows]

        # BEBIDAS
        cur.execute("""
            SELECT
                mb.id_menu_bebidas   AS id,
                mb.nombre_bebida     AS nombre,
                mb.precio            AS precio,
                mb.imagen_url        AS "imagenUrl",
                cb.nombre_categoria  AS categoria
            FROM menu_de_bebidas mb
            INNER JOIN categoria_bebidas cb
                ON cb.id_categoria_bebidas = mb.id_categoria_bebidas
            ORDER BY cb.nombre_categoria, mb.nombre_bebida;
        """)
        bebidas_rows = cur.fetchall()

        bebidas = [{    
            "id": r[0],
            "nombre": r[1],
            "precio": float(r[2]) if r[2] is not None else 0,
            "imagenUrl": r[3],
            "categoria": r[4],
            "tipo": "bebida"
        } for r in bebidas_rows]

        return jsonify({"platos": platos, "bebidas": bebidas})

    except Exception as e:
        print("MENU ERROR:", e)
        return jsonify({"success": False, "message": "Error cargando menú"}), 500

    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass


@app.route("/pedido", methods=["POST"])
def crear_pedido():
    data = request.get_json() or {}

    id_usuario = data.get("id_usuario")
    mesa = data.get("mesa")
    items = data.get("items") or []

    if not mesa or not isinstance(items, list) or len(items) == 0:
        return jsonify({"success": False, "message": "Mesa e items son requeridos"}), 400

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1) Crear venta
        monto_total = sum((float(i.get("precio", 0)) * int(i.get("cantidad", 0))) for i in items)

        cur.execute(
            "INSERT INTO venta (monto_total) VALUES (%s) RETURNING id_ventas;",
            (monto_total,)
        )
        id_venta = cur.fetchone()[0]

        # 2) (Opcional) Crear/registrar cliente por mesa en tabla clientes
        # MVP: si no quieres clientes, ponlo NULL.
        id_cliente = None

        # 3) Insertar detalle (N filas)
        for it in items:
            tipo = it.get("tipo")
            item_id = it.get("id")
            cantidad = int(it.get("cantidad", 1))
            precio = float(it.get("precio", 0))
            nombre = (it.get("nombre") or "").strip()

            id_menu_platos = item_id if tipo == "plato" else None
            id_menu_bebidas = item_id if tipo == "bebida" else None

            cur.execute("""
                INSERT INTO ventas_clientes_menu_bebidas_menu_platos
                  (id_ventas, id_menu_bebidas, id_menu_platos, id_clientes, cantidad, nombre_bebida, nombre_plato, precio)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                id_venta,
                id_menu_bebidas,
                id_menu_platos,
                id_cliente,
                cantidad,
                nombre if tipo == "bebida" else None,
                nombre if tipo == "plato" else None,
                precio
            ))

        conn.commit()
        return jsonify({"success": True, "id_venta": id_venta})

    except Exception as e:
        if conn:
            conn.rollback()
        print("PEDIDO ERROR:", e)
        return jsonify({"success": False, "message": "Error creando pedido"}), 500

    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

@app.route("/realizarPedido", methods=["POST"])
def realizar_pedido():
    data = request.get_json() or {}
    mesa = data.get("mesa")
    items = data.get("items") or []

    if not mesa or not items:
        return jsonify({"success": False, "message": "mesa e items son requeridos"}), 400

    conn = get_connection()
    if not conn:
        return jsonify({"success": False, "message": "No hay conexión a la DB"}), 500

    try:
        cur = conn.cursor()

        # 1) asegurar mesa
        cur.execute("""
            INSERT INTO mesas (numero)
            VALUES (%s)
            ON CONFLICT (numero) DO NOTHING
            RETURNING id_mesa;
        """, (mesa,))
        row = cur.fetchone()

        if row:
            id_mesa = row[0]
        else:
            cur.execute("SELECT id_mesa FROM mesas WHERE numero = %s;", (mesa,))
            id_mesa = cur.fetchone()[0]

        # 2) crear venta (monto_total lo calculamos)
        monto_total = 0

        # Para calcular total, traemos el precio real de la DB
        for it in items:
            tipo = it.get("tipo")
            item_id = it.get("id")
            cantidad = int(it.get("cantidad") or 0)
            if cantidad <= 0:
                continue

            if tipo == "plato":
                cur.execute("SELECT nombre_plato, precio FROM menu_de_platos WHERE id_menu_platos = %s;", (item_id,))
            else:
                cur.execute("SELECT nombre_bebida, precio FROM menu_de_bebidas WHERE id_menu_bebidas = %s;", (item_id,))

            r = cur.fetchone()
            if not r:
                continue

            nombre, precio = r[0], float(r[1])
            monto_total += precio * cantidad

        cur.execute("""
            INSERT INTO venta (monto_total, perdidas, ganancias)
            VALUES (%s, 0, %s)
            RETURNING id_ventas;
        """, (monto_total, monto_total))

        id_ventas = cur.fetchone()[0]

        # 3) insertar detalle
        for it in items:
            tipo = it.get("tipo")
            item_id = it.get("id")
            cantidad = int(it.get("cantidad") or 0)
            if cantidad <= 0:
                continue

            if tipo == "plato":
                cur.execute("SELECT nombre_plato, precio FROM menu_de_platos WHERE id_menu_platos = %s;", (item_id,))
                r = cur.fetchone()
                if not r:
                    continue
                nombre_plato, precio = r[0], r[1]

                cur.execute("""
                    INSERT INTO ventas_clientes_menu_bebidas_menu_platos
                    (id_ventas, id_menu_platos, id_menu_bebidas, id_clientes, id_mesa, cantidad, nombre_plato, nombre_bebida, precio)
                    VALUES (%s, %s, NULL, NULL, %s, %s, %s, NULL, %s);
                """, (id_ventas, item_id, id_mesa, cantidad, nombre_plato, precio))

            else:
                cur.execute("SELECT nombre_bebida, precio FROM menu_de_bebidas WHERE id_menu_bebidas = %s;", (item_id,))
                r = cur.fetchone()
                if not r:
                    continue
                nombre_bebida, precio = r[0], r[1]

                cur.execute("""
                    INSERT INTO ventas_clientes_menu_bebidas_menu_platos
                    (id_ventas, id_menu_platos, id_menu_bebidas, id_clientes, id_mesa, cantidad, nombre_plato, nombre_bebida, precio)
                    VALUES (%s, NULL, %s, NULL, %s, %s, NULL, %s, %s);
                """, (id_ventas, item_id, id_mesa, cantidad, nombre_bebida, precio))

        conn.commit()
        return jsonify({"success": True, "id_ventas": id_ventas, "mesa": mesa, "total": monto_total})

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
