import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ Falta DATABASE_URL en tu .env")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")
