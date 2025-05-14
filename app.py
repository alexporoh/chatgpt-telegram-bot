import os
import openai
import requests
from flask import Flask, request
import psycopg2

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

openai.api_key = OPENAI_API_KEY

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def create_users_table():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Таблица users создана или уже существует.")
    except Exception as e:
        print("❌ Ошибка при создании таблицы:", e)

def save_user(chat_id, username):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (chat_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING", (chat_id, username))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("DB error:", e)

def get_gpt_response(message):
    from app_extensions import get_system_prompt

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": message}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return "Ошибка генерации ответа: " + str(e)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        username = data["message"]["chat"].get("username", "unknown")
        text = data["message"].get("text", "")

        save_user(chat_id, username)
        reply = get_gpt_response(text)

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })
    return "ok"

create_users_table()

from app_extensions import init_admin_routes
init_admin_routes(app)