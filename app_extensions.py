import os
import threading
import requests
from flask import request, render_template, redirect, abort, make_response
from werkzeug.utils import secure_filename
from database import get_all_users
from config import TELEGRAM_TOKEN, STATIC_FOLDER

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dermapen123")

def get_db_connection():
    import psycopg2
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')

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

    def send_broadcast(text, image_path, chat_ids):
        for user_id in chat_ids:
            try:
                if image_path:
                    with open(image_path, "rb") as photo:
                        resp = requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                            data={"chat_id": user_id, "caption": text or ""},
                            files={"photo": photo}
                        )
                else:
                    resp = requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        json={"chat_id": user_id, "text": text}
                    )
                result = resp.json()
                if not result.get("ok"):
                    print(f"Ошибка для {user_id}: {result}")
            except Exception as e:
                print(f"Ошибка при отправке пользователю {user_id}:", e)

    create_admin_tables()

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

        if image and image.filename:
            filename = secure_filename(image.filename)
            os.makedirs(STATIC_FOLDER, exist_ok=True)
            image_path = os.path.join(STATIC_FOLDER, filename)
            image.save(image_path)

        chat_ids = get_all_chat_ids()
        thread = threading.Thread(target=send_broadcast, args=(text, image_path, chat_ids))
        thread.start()

        html = """<html><body style='font-family:sans-serif; padding:20px;'>
        <h2>Рассылка запущена 🚀</h2>
        <p>Вы можете закрыть страницу — сообщения будут отправлены в фоновом режиме.</p>
        <a href='/admin?password=dermapen123' style='display:inline-block;margin-top:20px;'>⬅ Вернуться в админку</a>
        </body></html>"""
        return make_response(html)