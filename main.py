from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import requests
import json
import threading

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_DOMAIN") + "/webhook"

FIREBASE_DB_FILE = "firebase_links.json"

# === UTILS ===
def load_links():
    try:
        with open(FIREBASE_DB_FILE) as f:
            return json.load(f)
    except:
        return []

def save_links(links):
    with open(FIREBASE_DB_FILE, "w") as f:
        json.dump(links, f)

# === TELEGRAM BOT ===
bot_app = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return await update.message.reply_text("❌")
    await update.message.reply_text("🔥 Bot running.\nUse /status, /add <link>, /clear")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    links = load_links()
    await update.message.reply_text(f"📌 DBs: {len(links)}\n🟢 Active.")

async def add_firebase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("🔗 /add https://db.firebaseio.com/path")
    url = " ".join(context.args)
    if "firebaseio.com" not in url: return await update.message.reply_text("❌ Invalid.")
    links = load_links()
    if url not in links:
        links.append(url)
        save_links(links)
        await update.message.reply_text(f"✅ Added:\n{url}")
    else:
        await update.message.reply_text("📍 Already added.")

async def clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_links([])
    await update.message.reply_text("🗑 Cleared.")

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), bot_app.bot)
    bot_app.create_task(bot_app.process_update(update))
    return "OK", 200

@app.route("/health")
def health():
    return {"status": "alive", "bots": 1}, 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def main_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).updater(None).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("status", status))
    bot_app.add_handler(CommandHandler("add", add_firebase))
    bot_app.add_handler(CommandHandler("clear", clear_all))
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    await bot_app.initialize()
    await bot_app.start()
    threading.Thread(target=run_web, daemon=True).start()
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_bot())
