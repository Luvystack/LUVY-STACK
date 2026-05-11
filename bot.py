import os
import json
import time
import requests
import subprocess

# =========================
# CONFIG
# =========================
TOKEN = "8738323399:AAEisCBZay6ChA7ghLCfbyt7syG_KxT2AGw"
ADMIN_ID = 7939923484

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
# TELEGRAM
# =========================
def send(chat_id, text):
    try:
        requests.post(
            BASE_URL + "/sendMessage",
            data={"chat_id": chat_id, "text": text}
        )
    except:
        pass

last_update_id = None

def get_updates():
    global last_update_id
    url = BASE_URL + "/getUpdates"

    if last_update_id:
        url += f"?offset={last_update_id + 1}"

    return requests.get(url).json()

# =========================
# ENGINE CORE
# =========================
def deploy_app(name, file):
    path = f"deploy/{file}"

    if not os.path.exists(path):
        return "❌ File not found in deploy/"

    log_path = f"logs/{name}.log"

    log_file = open(log_path, "a")

    process = subprocess.Popen(
        ["python3", path],
        stdout=log_file,
        stderr=log_file
    )

    apps[name] = {
        "file": file,
        "pid": process.pid,
        "log": log_path,
        "status": "running"
    }

    save_db(apps)

    return f"""🚀 DEPLOYED
Name: {name}
PID: {process.pid}
Status: running"""

def stop_app(name):
    if name not in apps:
        return "❌ App not found"

    try:
        os.kill(apps[name]["pid"], 9)
        apps[name]["status"] = "stopped"
        save_db(apps)
        return f"🛑 {name} stopped"
    except:
        return "❌ Failed to stop process"

def list_apps():
    if not apps:
        return "No running apps"

    text = "📦 LUVY STACK APPS\n\n"

    for k, v in apps.items():
        text += f"• {k}\n  PID: {v['pid']}\n  Status: {v['status']}\n\n"

    return text

def get_logs(name):
    if name not in apps:
        return "❌ App not found"

    path = apps[name]["log"]

    if not os.path.exists(path):
        return "No logs yet"

    with open(path, "r") as f:
        return f.read()[-3000:]

# =========================
# STARTUP MESSAGE
# =========================
print("⚡ LUVY STACK ENGINE ONLINE")

MENU = """⚡ LUVY STACK ENGINE

Commands:
• /deploy name file.py
• /apps
• /logs name
• /stop name
• /ping
"""

# =========================
# MAIN LOOP
# =========================
while True:
    try:
        data = get_updates()

        for update in data.get("result", []):
            last_update_id = update["update_id"]

            msg = update.get("message")
            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")

            # ONLY ADMIN
            if user_id != ADMIN_ID:
                send(chat_id, "❌ Access denied")
                continue

            # =========================
            # START
            # =========================
            if text == "/start":
                send(chat_id, MENU)

            # =========================
            # DEPLOY
            # =========================
            elif text.startswith("/deploy"):
                parts = text.split()

                if len(parts) < 3:
                    send(chat_id, "Usage: /deploy name file.py")
                    continue

                send(chat_id, deploy_app(parts[1], parts[2]))

            # =========================
            # APPS
            # =========================
            elif text == "/apps":
                send(chat_id, list_apps())

            # =========================
            # LOGS
            # =========================
            elif text.startswith("/logs"):
                parts = text.split()

                if len(parts) < 2:
                    send(chat_id, "Usage: /logs name")
                    continue

                send(chat_id, get_logs(parts[1]))

            # =========================
            # STOP
            # =========================
            elif text.startswith("/stop"):
                parts = text.split()

                if len(parts) < 2:
                    send(chat_id, "Usage: /stop name")
                    continue

                send(chat_id, stop_app(parts[1]))

            # =========================
            # PING
            # =========================
            elif text == "/ping":
                send(chat_id, "pong 🟢 LUVY STACK ONLINE")

            # =========================
            # DEFAULT
            # =========================
            else:
                send(chat_id, MENU)

    except Exception as e:
        print("error:", e)

    time.sleep(2)