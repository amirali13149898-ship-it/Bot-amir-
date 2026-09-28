import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# آیدی عددی ادمین‌ها، با کاما جدا کن: 123,456
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# روی Render خودکار ست میشه. اگه خالی باشه ربات با polling اجرا میشه (برای تست لوکال)
BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("BASE_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "hmbotsecret")  # فقط A-Z a-z 0-9 _ -
PORT = int(os.getenv("PORT", "10000"))
