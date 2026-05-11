import os
import json
import time
import requests
import subprocess
import signal
import random
import string

# =========================
# CONFIG
# =========================
TOKEN = "8738323399:AAEisCBZay6ChA7ghLCfbyt7syG_KxT2AGw"
ADMIN_ID = 7939923484

# LSX MANAGER BOT (username: @lsxmanagerbot)
MANAGER_CHAT_ID = "@lsxmanagerbot"
MANAGER_BOT_TOKEN = "8579949602:AAGT3swfTtCfcESaxz-prCBuReejrFPDLJQ"

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
MANAGER_URL = f"https://api.telegram.org/bot{MANAGER_BOT_TOKEN}"

DB_FILE = "storage/apps.json"

os.makedirs("deploy", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("storage", exist_ok=True)

# =========================
# SECURITY TOKEN SYSTEM
# =========================
CURRENT_TOKEN = None
LAST_TOKEN_TIME = 0

def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def rotate_token():
    global CURRENT_TOKEN, LAST_TOKEN_TIME

    now = time.time()
    if CURRENT_TOKEN is None or now - LAST_TOKEN_TIME >= 600:  # 10 minutes

        CURRENT_TOKEN = generate_token()
        LAST_TOKEN_TIME = now

        msg = f"🔐 NEW DEPLOY TOKEN:\n{CURRENT_TOKEN}"

        # send to admin
        send(ADMIN_ID, msg)

        # send to manager bot
        try:
            requests.post(
                MANAGER_URL + "/sendMessage",
                data={"chat_id": MANAGER_CHAT_ID, "text": msg},
                timeout=10
            )
        except:
            pass

# =========================
# DB
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
# TELEGRAM HELPERS
# =========================
def send(chat_id, text):
    try:
        requests.post(
            BASE_URL + "/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except:
        pass

def get_updates(offset=None):
    try:
        url = BASE_URL + "/getUpdates"
        if offset:
            url += f"?offset={offset}"
        return requests.get(url, timeout=10).json()
    except:
        return {"result": []}

# =========================
# SAFETY SCANNER
# =========================
def scan_code(code):
    blocked = ["rm -rf", "socket", "fork", "kill"]

    for b in blocked:
        if b in code:
            return False, f"Blocked: {b}"

    try:
        compile(code, "<string>", "exec")
    except Exception as e:
        return False, str(e)

    return True, "OK"

# =========================
# ENGINE CORE (ISOLATED)
# =========================
def deploy_app(name, code):
    path = f"deploy/{name}.py"
    log_path = f"logs/{name}.log"

    ok, reason = scan_code(code)
    if not ok:
        return f"❌ Code blocked\n{reason}"

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
    except:
        return "❌ Failed to save code"

    try:
        log_file = open(log_path, "a")

        process = subprocess.Popen(
            ["python3", path],
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid
        )

    except Exception as e:
        return f"❌ Deploy failed: {e}"

    apps[name] = {
        "file": path,
        "pid": process.pid,
        "log": log_path,
        "status": "running"
    }

    save_db(apps)

    return f"🚀 DEPLOYED: {name}"

# =========================
# STOP
# =========================
def stop_app(name):
    if name not in apps:
        return "❌ Not found"

    try:
        pid = apps[name]["pid"]
        os.killpg(os.getpgid(pid), signal.SIGTERM)

        apps[name]["status"] = "stopped"
        save_db(apps)

        return f"🛑 Stopped: {name}"

    except Exception as e:
        return f"❌ Failed: {e}"

# =========================
# LOGS
# =========================
def get_logs(name):
    if name not in apps:
        return "❌ App not found"

    try:
        with open(apps[name]["log"], "r") as f:
            return f.read()[-3000:]
    except:
        return "No logs yet"

def list_apps():
    if not apps:
        return "No apps running"

    text = "📦 LUVY STACK DASHBOARD\n━━━━━━━━━━━━━━\n"

    for k, v in apps.items():
        text += f"• {k} → {v['status']}\n"

    return text + "\n━━━━━━━━━━━━━━"

# =========================
# STATE
# =========================
last_update_id = 0
pending_code = {}

print("⚡ LUVY STACK ENGINE RUNNING")

MENU = """
⚡ LUVY STACK ENGINE

Flow:
1. /deploy name
2. send: TOKEN + code

Commands:
• /deploy name
• /apps
• /logs name
• /stop name
• /dashboard
• /ping
"""

# =========================
# LOOP
# =========================
while True:
    try:
        rotate_token()  # 🔥 TOKEN REFRESH SYSTEM

        updates = get_updates(last_update_id)

        for update in updates.get("result", []):
            last_update_id = update["update_id"] + 1

            msg = update.get("message")
            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")

            if user_id != ADMIN_ID:
                send(chat_id, "❌ Access denied")
                continue

            if text == "/start":
                send(chat_id, MENU)

            elif text.startswith("/deploy "):
                name = text.split(" ", 1)[1].strip()
                pending_code[user_id] = name
                send(chat_id, f"📥 Send:\nTOKEN + code for {name}")

            elif user_id in pending_code:
                name = pending_code.pop(user_id)

                parts = text.split("\n", 1)

                if len(parts) < 2:
                    send(chat_id, "❌ Format:\nTOKEN\nCODE")
                    continue

                token = parts[0].strip()
                code = parts[1]

                if token != CURRENT_TOKEN:
                    send(chat_id, "❌ Invalid token")
                    continue

                send(chat_id, deploy_app(name, code))

            elif text == "/apps":
                send(chat_id, list_apps())

            elif text == "/dashboard":
                send(chat_id, list_apps())

            elif text.startswith("/logs"):
                parts = text.split()
                if len(parts) < 2:
                    send(chat_id, "Usage: /logs name")
                    continue
                send(chat_id, get_logs(parts[1]))

            elif text.startswith("/stop"):
                parts = text.split()
                if len(parts) < 2:
                    send(chat_id, "Usage: /stop name")
                    continue
                send(chat_id, stop_app(parts[1]))

            elif text == "/ping":
                send(chat_id, "pong 🟢 LUVY STACK ONLINE")

            else:
                send(chat_id, MENU)

    except Exception as e:
        print("error:", e)

    time.sleep(2)