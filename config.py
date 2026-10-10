import os
import re

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# آیدی عددی ادمین‌ها، با کاما جدا کن: 123,456
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# روی Render خودکار ست میشه. اگه خالی باشه ربات با polling اجرا میشه (برای تست لوکال)
BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", "10000"))

# بدون مقدار پیش‌فرض! تو Render یه رشته‌ی تصادفی بلند بذار (حداقل ۳۲ کاراکتر، فقط A-Z a-z 0-9 _ -)
# مثلاً با این دستور بساز: python -c "import secrets; print(secrets.token_urlsafe(32))"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
if BASE_URL and (len(WEBHOOK_SECRET) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", WEBHOOK_SECRET)):
    raise RuntimeError(
        "WEBHOOK_SECRET باید تو Environment Variables ست بشه: حداقل ۳۲ کاراکتر و فقط A-Z a-z 0-9 _ -"
    )
