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

MANAGER_BOT_TOKEN = "YOUR_MANAGER_BOT_TOKEN"
MANAGER_CHAT_ID = "@lsxmanagerbot"

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
MANAGER_URL = f"https://api.telegram.org/bot{MANAGER_BOT_TOKEN}"

DB_FILE = "storage/apps.json"

os.makedirs("deploy", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("storage", exist_ok=True)

# =========================
# STATE
# =========================
ENGINE_LOCKED = True
ENGINE_PASSWORD = "LUVY-SECURE-ACCESS"

CURRENT_TOKEN = None
LAST_TOKEN_TIME = 0

last_update_id = 0
pending_code = {}

apps = {}

# =========================
# DB
# =========================
def load_db():
    global apps
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                apps = json.load(f)
        except:
            apps = {}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(apps, f, indent=2)

load_db()

# =========================
# TELEGRAM HELPERS
# =========================
def send(chat_id, text):
    try:
        requests.post(BASE_URL + "/sendMessage",
                      data={"chat_id": chat_id, "text": text},
                      timeout=10)
    except:
        pass

def manager_send(text):
    try:
        requests.post(MANAGER_URL + "/sendMessage",
                      data={"chat_id": MANAGER_CHAT_ID, "text": text},
                      timeout=10)
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
# TOKEN SYSTEM (ONLY MANAGER)
# =========================
def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def rotate_token():
    global CURRENT_TOKEN, LAST_TOKEN_TIME

    now = time.time()
    if CURRENT_TOKEN is None or now - LAST_TOKEN_TIME >= 600:
        CURRENT_TOKEN = generate_token()
        LAST_TOKEN_TIME = now

        msg = f"🔐 NEW DEPLOY TOKEN:\n{CURRENT_TOKEN}"
        manager_send(msg)   # ONLY manager gets it

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
# DEPLOY ENGINE
# =========================
def deploy_app(name, code):
    path = f"deploy/{name}.py"
    log_path = f"logs/{name}.log"

    ok, reason = scan_code(code)
    if not ok:
        return f"❌ BLOCKED\n{reason}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)

    log_file = open(log_path, "a")

    process = subprocess.Popen(
        ["python3", path],
        stdout=log_file,
        stderr=log_file,
        preexec_fn=os.setsid
    )

    apps[name] = {
        "file": path,
        "pid": process.pid,
        "log": log_path,
        "status": "running"
    }

    save_db()

    return f"🚀 DEPLOYED: {name}"

# =========================
# STOP
# =========================
def stop_app(name):
    if name not in apps:
        return "❌ Not found"

    try:
        os.killpg(os.getpgid(apps[name]["pid"]), signal.SIGTERM)
        apps[name]["status"] = "stopped"
        save_db()
        return f"🛑 Stopped: {name}"
    except:
        return "❌ Failed"

# =========================
# DASHBOARD
# =========================
def dashboard():
    if not apps:
        return "No apps"

    text = "📦 LUVY STACK DASHBOARD\n━━━━━━━━━━━━━━\n"
    for k, v in apps.items():
        text += f"• {k} → {v['status']}\n"
    return text

# =========================
# LOCK CONTROL
# =========================
def unlock(password):
    global ENGINE_LOCKED
    if password == ENGINE_PASSWORD:
        ENGINE_LOCKED = False
        return "🔓 Unlocked"
    return "❌ Wrong password"

# =========================
# UI STATE
# =========================
def start_screen():
    status = "🔒 LOCKED" if ENGINE_LOCKED else "🟢 ACTIVE"
    return f"LUVY STACK ENGINE\nSTATUS: {status}"

# =========================
# LOOP
# =========================
print("LUVY STACK ENGINE RUNNING")

while True:
    try:
        rotate_token()

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
                continue

            # START (ONLY STATUS)
            if text == "/start":
                send(chat_id, start_screen())
                continue

            # UNLOCK
            if text.startswith("/unlock"):
                parts = text.split()
                if len(parts) < 2:
                    send(chat_id, "Usage: /unlock password")
                    continue
                send(chat_id, unlock(parts[1]))
                continue

            # BLOCK EVERYTHING WHEN LOCKED
            if ENGINE_LOCKED:
                send(chat_id, "🔒 SYSTEM LOCKED")
                continue

            # DEPLOY
            if text.startswith("/deploy "):
                name = text.split(" ", 1)[1]
                pending_code[user_id] = name
                send(chat_id, f"📥 Send code for: {name}")

            elif user_id in pending_code:
                name = pending_code.pop(user_id)

                parts = text.split("\n", 1)
                if len(parts) < 2:
                    send(chat_id, "❌ Send TOKEN + CODE")
                    continue

                token = parts[0].strip()
                code = parts[1]

                if token != CURRENT_TOKEN:
                    send(chat_id, "❌ Invalid token")
                    continue

                send(chat_id, deploy_app(name, code))

            elif text == "/dashboard":
                send(chat_id, dashboard())

            elif text.startswith("/stop"):
                parts = text.split()
                send(chat_id, stop_app(parts[1]) if len(parts) > 1 else "Usage: /stop name")

    except Exception as e:
        print("error:", e)

    time.sleep(2)