from flask import request, render_template, redirect, abort
import os
import requests
import psycopg2
from werkzeug.utils import secure_filename

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
STATIC_FOLDER = "static"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dermapen123")  # Пароль по умолчанию

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def get_system_prompt():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='system_prompt'")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "Ты — дружелюбный помощник."

def get_user_count():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count

def init_admin_routes(app):

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

    def check_access():
        password = request.args.get("password")
        if password != ADMIN_PASSWORD:
            abort(403)

    @app.route("/admin", methods=["GET"])
    def admin():
        check_access()
        current_prompt = get_system_prompt()
        user_count = get_user_count()
        return render_template("admin.html", current_prompt=current_prompt, user_count=user_count)

    @app.route("/save_prompt", methods=["POST"])
    def save_prompt():
        check_access()
        prompt = request.form.get("prompt", "").strip()
        if prompt:
            set_system_prompt(prompt)
        return redirect(f"/admin?password={ADMIN_PASSWORD}")

    @app.route("/broadcast", methods=["POST"])
    def broadcast():
        check_access()
        text = request.form.get("text", "").strip()
        image = request.files.get("image")
        image_path = None

        if image:
            filename = secure_filename(image.filename)
            os.makedirs(STATIC_FOLDER, exist_ok=True)
            image_path = os.path.join(STATIC_FOLDER, filename)
            image.save(image_path)
            print("Изображение сохранено:", image_path)

        chat_ids = get_all_chat_ids()
        for chat_id in chat_ids:
            try:
                if image_path:
                    with open(image_path, "rb") as photo:
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                            data={"chat_id": chat_id},
                            files={"photo": photo}
                        )
                if text:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": text
                    })
            except Exception as e:
                print(f"Ошибка при отправке {chat_id}:", e)

        return redirect(f"/admin?password={ADMIN_PASSWORD}")