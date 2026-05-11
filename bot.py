import os
import json
import time
import requests
import subprocess
import signal

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
# SAFETY SCANNER (light)
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
# ENGINE CORE
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
# STOP APP
# =========================
def stop_app(name):
    if name not in apps:
        return "❌ Not found"

    try:
        os.killpg(os.getpgid(apps[name]["pid"]), signal.SIGTERM)
        apps[name]["status"] = "stopped"
        save_db(apps)
        return f"🛑 Stopped: {name}"
    except:
        return "❌ Failed"

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

# =========================
# LIST APPS
# =========================
def list_apps():
    if not apps:
        return "No apps running"

    text = "📦 LUVY STACK DASHBOARD\n━━━━━━━━━━━━━━\n"

    for k, v in apps.items():
        text += f"• {k} → {v['status']}\n"

    return text

# =========================
# STATE
# =========================
last_update_id = 0
pending_code = {}

print("⚡ LUVY STACK RUNTIME ENGINE RUNNING")

MENU = """
⚡ LUVY STACK ENGINE

Commands:
• /upload (optional)
• /deploy name
• /apps
• /logs name
• /stop name
• /dashboard
• /ping
"""

# =========================
# MAIN LOOP
# =========================
while True:
    try:
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

            # START
            if text == "/start":
                send(chat_id, MENU)

            # DEPLOY FLOW
            elif text.startswith("/deploy "):
                name = text.split(" ", 1)[1].strip()
                pending_code[user_id] = name
                send(chat_id, f"📥 Send code for: {name}")

            elif user_id in pending_code:
                name = pending_code.pop(user_id)
                send(chat_id, deploy_app(name, text))

            # OPTIONAL FILE UPLOAD (simple storage only)
            elif text == "/upload":
                send(chat_id, "📤 Send .py file")

            elif "document" in msg:
                file_id = msg["document"]["file_id"]
                file_name = msg["document"]["file_name"]

                r = requests.get(BASE_URL + f"/getFile?file_id={file_id}").json()
                file_path = r["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                code = requests.get(file_url).text

                path = f"deploy/{file_name}"
                with open(path, "w", encoding="utf-8") as f:
                    f.write(code)

                send(chat_id, f"✅ Uploaded: {file_name}")

            # APPS
            elif text == "/apps":
                send(chat_id, list_apps())

            # DASHBOARD
            elif text == "/dashboard":
                send(chat_id, list_apps())

            # LOGS
            elif text.startswith("/logs"):
                parts = text.split()
                send(chat_id, get_logs(parts[1]) if len(parts) > 1 else "Usage: /logs name")

            # STOP
            elif text.startswith("/stop"):
                parts = text.split()
                send(chat_id, stop_app(parts[1]) if len(parts) > 1 else "Usage: /stop name")

            # PING
            elif text == "/ping":
                send(chat_id, "pong 🟢 LUVY STACK ONLINE")

            else:
                send(chat_id, MENU)

    except Exception as e:
        print("error:", e)

    time.sleep(2)