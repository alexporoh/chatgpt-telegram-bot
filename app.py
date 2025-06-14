import os
import openai
import requests
from flask import Flask, request
import psycopg2

from app_extensions import init_admin_routes, get_system_prompt

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dialogs (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                role TEXT CHECK (role IN ('user', 'assistant')),
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Таблицы users и dialogs готовы.")
    except Exception as e:
        print("❌ Ошибка при создании таблиц:", e)

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

def save_dialog(chat_id, role, message):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO dialogs (chat_id, role, message) VALUES (%s, %s, %s)", (chat_id, role, message))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Ошибка сохранения диалога:", e)

def load_last_dialog(chat_id, limit=5):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, message FROM dialogs
        WHERE chat_id = %s
        ORDER BY timestamp DESC
        LIMIT %s
    """, (chat_id, limit * 2))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return list(reversed(rows))

def get_gpt_response(chat_id, user_message):
    history = [{"role": "system", "content": get_system_prompt()}]
    dialog = load_last_dialog(chat_id)
    history.extend({"role": r, "content": m} for r, m in dialog)
    history.append({"role": "user", "content": user_message})

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0125",
            messages=history
        )
        response = completion.choices[0].message.content.strip()
        return response
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

        if text.strip() == "/start":
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                "chat_id": chat_id,
                "text": "Консультант от Dermapen Russia готов к вашим вопросам."
            })

        reply = get_gpt_response(chat_id, text)

        save_dialog(chat_id, "user", text)
        save_dialog(chat_id, "assistant", reply)

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    return "ok"

create_users_table()
init_admin_routes(app)