import os
import json
import time
import requests
import subprocess

# =========================
# CONFIG
# =========================
TOKEN = "8738323399:AAEisCBZay6ChA7ghLCfbyt7syG_KxT2AGw"
ADMIN_ID = 123456789  # replace with your Telegram ID

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

DB_FILE = "storage/apps.json"

os.makedirs("deploy", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("storage", exist_ok=True)

# =========================
# DATABASE
# =========================
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

apps = load_db()

# =========================
# TELEGRAM SEND
# =========================
def send(chat_id, text):
    try:
        requests.post(
            BASE_URL + "/sendMessage",
            data={"chat_id": chat_id, "text": text}
        )
    except:
        pass

# =========================
# GET UPDATES
# =========================
last_update_id = None

def get_updates():
    global last_update_id
    url = BASE_URL + "/getUpdates"

    if last_update_id:
        url += f"?offset={last_update_id + 1}"

    return requests.get(url).json()

# =========================
# DEPLOY SYSTEM
# =========================
def deploy_app(name, file):
    path = f"deploy/{file}"

    if not os.path.exists(path):
        return "❌ File not found"

    process = subprocess.Popen(["python3", path])

    apps[name] = {
        "file": file,
        "pid": process.pid,
        "status": "running"
    }

    save_db(apps)

    return f"🚀 Deployed {name} (PID {process.pid})"

# =========================
# MAIN ENGINE
# =========================
print("🟢 LUVY STACK RUNNING")

while True:
    try:
        data = get_updates()

        for update in data.get("result", []):
            last_update_id = update["update_id"]

            if "message" not in update:
                continue

            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")

            # ADMIN ONLY
            if user_id != ADMIN_ID:
                send(chat_id, "❌ Access denied")
                continue

            # COMMANDS
            if text.startswith("/deploy"):
                parts = text.split()

                if len(parts) < 3:
                    send(chat_id, "Usage: /deploy name file.py")
                    continue

                name = parts[1]
                file = parts[2]

                result = deploy_app(name, file)
                send(chat_id, result)

            elif text == "/apps":
                send(chat_id, str(apps))

            elif text == "/ping":
                send(chat_id, "pong 🟢")

            else:
                send(chat_id, "Commands: /deploy /apps /ping")

    except Exception as e:
        print("Error:", e)

    time.sleep(2)