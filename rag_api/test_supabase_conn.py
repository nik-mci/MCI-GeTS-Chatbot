import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv("SUPABASE_CONNECTION_STRING")

print(f"Testing connection to: {conn_str.split('@')[-1]}")
try:
    conn = psycopg2.connect(conn_str)
    print("✅ Connection Successful!")
    conn.close()
except Exception as e:
    print(f"❌ Connection Failed: {e}")
