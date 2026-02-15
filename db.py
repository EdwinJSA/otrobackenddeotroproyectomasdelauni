import psycopg2
import os
from dotenv import load_dotenv

# cargar variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL no está definida en .env")

# tu SQL aquí
SQL_SCRIPT = """
-- 1) crear tabla mesas (si no existe)
CREATE TABLE IF NOT EXISTS mesas (
  id_mesa BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  numero  INT NOT NULL UNIQUE
);

-- 2) insertar mesas 1..4 (opcional)
INSERT INTO mesas (numero)
VALUES (1),(2),(3),(4)
ON CONFLICT (numero) DO NOTHING;

-- 3) agregar columna id_mesa al detalle (si no existe)
ALTER TABLE ventas_clientes_menu_bebidas_menu_platos
ADD COLUMN IF NOT EXISTS id_mesa BIGINT NULL REFERENCES mesas(id_mesa);


"""

def ejecutar_sql():
    conn = None

    try:
        print("🔌 Conectando a Render PostgreSQL...")

        conn = psycopg2.connect(DATABASE_URL)

        cursor = conn.cursor()

        print("⚙️ Ejecutando SQL...")

        cursor.execute(SQL_SCRIPT)

        conn.commit()

        print("✅ SQL ejecutado correctamente")

    except Exception as e:

        print("❌ Error ejecutando SQL:")
        print(e)

        if conn:
            conn.rollback()

    finally:

        if conn:
            cursor.close()
            conn.close()
            print("🔒 Conexión cerrada")

if __name__ == "__main__":
    ejecutar_sql()
