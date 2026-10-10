import asyncio
import json
import os
import threading
from urllib.parse import urlparse

from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN", "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
FIREBASE_DB_FILE = "firebase_links.json"

bot_app = None


def load_links():
    try:
        with open(FIREBASE_DB_FILE, "r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_links(links):
    with open(FIREBASE_DB_FILE, "w", encoding="utf-8") as file:
        json.dump(links, file, indent=2)


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and ADMIN_ID_RAW.isdigit() and user.id == int(ADMIN_ID_RAW))


def normalize_firebase_url(raw_url: str):
    raw_url = raw_url.strip()
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host.endswith(".firebaseio.com")
        or host.endswith(".firebasedatabase.app")
    ):
        return None
    return raw_url.rstrip("/")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("Access denied.")
        return
    await update.effective_message.reply_text(
        "Firebase Link Status Bot is running.\nUse /status, /add <Firebase URL>, or /clear."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("Access denied.")
        return
    links = load_links()
    await update.effective_message.reply_text(
        f"Saved Firebase database links: {len(links)}\n"
        "This bot stores links only; it does not retrieve phone numbers or OTPs."
    )


async def add_firebase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("Access denied.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /add https://your-project-default-rtdb.firebaseio.com/path"
        )
        return

    url = normalize_firebase_url(" ".join(context.args))
    if not url:
        await update.effective_message.reply_text(
            "Invalid URL. Use an HTTPS Firebase Realtime Database URL."
        )
        return

    links = load_links()
    if url in links:
        await update.effective_message.reply_text("That URL is already saved.")
        return

    links.append(url)
    save_links(links)
    await update.effective_message.reply_text("Firebase URL saved.")


async def clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("Access denied.")
        return
    save_links([])
    await update.effective_message.reply_text("Saved Firebase links cleared.")


@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
def health():
    return {"status": "alive"}, 200


@app.route("/webhook", methods=["POST"])
def webhook():
    if bot_app is None:
        return {"error": "bot is starting"}, 503
    payload = request.get_json(silent=True)
    if not payload:
        return {"error": "invalid update"}, 400
    update = Update.de_json(payload, bot_app.bot)
    bot_app.create_task(bot_app.process_update(update))
    return "OK", 200


def run_web():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


async def main_bot():
    global bot_app

    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN environment variable.")
    if not ADMIN_ID_RAW.isdigit():
        raise RuntimeError("Missing or invalid ADMIN_ID environment variable.")
    if not WEBHOOK_DOMAIN:
        raise RuntimeError(
            "Missing WEBHOOK_DOMAIN. Set it to your public Render service URL, "
            "for example https://your-service.onrender.com (no /webhook suffix)."
        )

    bot_app = Application.builder().token(BOT_TOKEN).updater(None).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("status", status))
    bot_app.add_handler(CommandHandler("add", add_firebase))
    bot_app.add_handler(CommandHandler("clear", clear_all))

    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(f"{WEBHOOK_DOMAIN}/webhook")

    threading.Thread(target=run_web, daemon=True).start()
    print(f"Health endpoint available on port {PORT}")

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await bot_app.bot.delete_webhook()
        await bot_app.stop()
        await bot_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main_bot())
    
