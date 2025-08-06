import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def get_all_users():
    """Возвращает список всех chat_id пользователей"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users")
    users = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return users