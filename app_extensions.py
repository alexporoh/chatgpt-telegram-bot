from flask import Flask, request, render_template, redirect
import os
import openai
import requests
import psycopg2

from werkzeug.utils import secure_filename

# --- Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
STATIC_FOLDER = "static"

openai.api_key = OPENAI_API_KEY

def init_admin_routes(app):

    def get_db_connection():
        return psycopg2.connect(DATABASE_URL, sslmode='require')

    # Создание таблиц
    def create_admin_tables():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()
        cur.close()
        conn.close()

    create_admin_tables()

    def get_system_prompt():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key='system_prompt'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else "Ты — дружелюбный помощник."

    def set_system_prompt(prompt):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO settings (key, value) VALUES ('system_prompt', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (prompt,))
        conn.commit()
        cur.close()
        conn.close()

    def get_all_chat_ids():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM users")
        ids = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return ids

    @app.route("/broadcast", methods=["POST"])
def broadcast():
    text = request.form.get("text", "").strip()
    image = request.files.get("image")
    image_url = None

    if image:
        filename = secure_filename(image.filename)
        os.makedirs("static", exist_ok=True)
        filepath = os.path.join("static", filename)
        image.save(filepath)

        image_url = f"https://chatgpt-telegram-bot-8jq0.onrender.com/static/{filename}"

    chat_ids = get_all_chat_ids()
    print("Рассылаем на", len(chat_ids), "пользователей")

    for chat_id in chat_ids:
        try:
            if image_url:
                resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={
                    "chat_id": chat_id,
                    "caption": text,
                    "photo": image_url
                })
            else:
                resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": text
                })
            print("→", chat_id, resp.status_code)
        except Exception as e:
            print("Ошибка отправки:", e)

    return redirect("/admin")