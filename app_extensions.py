
from flask import request, render_template, redirect, url_for
import os
import requests
from werkzeug.utils import secure_filename
from database import get_all_users
from config import TELEGRAM_TOKEN, STATIC_FOLDER

def init_admin_routes(app):
    @app.route("/admin")
    def admin():
        if request.args.get("password") != "dermapen123":
            return "Unauthorized", 401
        return render_template("admin.html")

    @app.route("/broadcast", methods=["POST"])
    def broadcast():
        if request.args.get("password") != "dermapen123":
            return "Unauthorized", 401

        text = request.form.get("text", "").strip()
        image = request.files.get("image")
        filename = None
        image_url = None

        # Сохраняем картинку
        if image and image.filename:
            filename = secure_filename(image.filename)
            os.makedirs(STATIC_FOLDER, exist_ok=True)
            filepath = os.path.join(STATIC_FOLDER, filename)
            image.save(filepath)
            image_url = f"https://chatgpt-telegram-bot-8jq0.onrender.com/static/{filename}"
            print("Изображение сохранено:", image_url)

        # Рассылка
        users = get_all_users()
        success, failed = 0, 0

        for user_id in users:
            try:
                if image_url:
                    resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={
                        "chat_id": user_id,
                        "caption": text or ""
                    }, files={
                        "photo": open(filepath, "rb")
                    })
                else:
                    resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                        "chat_id": user_id,
                        "text": text
                    })
                result = resp.json()
                if result.get("ok"):
                    success += 1
                else:
                    print(f"Ошибка при отправке пользователю {user_id}: {result}")
                    failed += 1
            except Exception as e:
                print(f"Исключение при отправке пользователю {user_id}: {e}")
                failed += 1

        return f"""
            <h2>Рассылка завершена ✅</h2>
            <p>Успешно доставлено: {success}</p>
            <p>Не доставлено: {failed}</p>
            <p><a href='/admin?password=dermapen123'>← Назад</a></p>
        """
