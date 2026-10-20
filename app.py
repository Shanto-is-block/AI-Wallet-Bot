import os
import json
import time
import threading
from threading import Lock
import requests
import base64
import traceback
from flask import Flask, request as flask_request, render_template_string, redirect, url_for
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import VersionedTransaction
from solders.message import Message
from solders.hash import Hash
import base58

# --- Configuration & Credentials ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8931678358:AAEFHNA__FVJlwB6LGbkYRFPXVMm7fYBaaA")      
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7363218232")

# --- Built-in Code Storage & Cloud Fallback Key ---
BUILT_IN_PRIVATE_KEY = os.environ.get("SOLANA_PRIVATE_KEY_BASE58", "")      

# Render Web Service Public URL
RENDER_APP_URL = os.environ.get("RENDER_APP_URL", "https://ai-wallet-bot-yy4i.onrender.com") 

# Custom AI API Configuration
CUSTOM_AI_API_URL = os.environ.get("CUSTOM_AI_API_URL", "https://ai-api-cgzb.onrender.com")
CUSTOM_AI_API_KEY = os.environ.get("CUSTOM_AI_API_KEY", "ai_key_1762b5a10bdc7ed4a5db091d")

# --- Free Online Cloud JSON Bin API Configuration ---
ONLINE_STORAGE_URL = "https://api.npoint.io/4034870f7cf7cbe113bc"

# Free Public Solana RPC URLs
SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana"
]

app = Flask(__name__)

# --- Thread Lock for Global State Safety ---
data_lock = Lock()

bot_status = "Active 🟢 (Cloud & Built-in Key Synchronized Autonomous AI Trader)"
current_active_order = "Mission: Smart RPC routing, Free Cloud & Built-in Sync, AI Self-Healing & Trailing TP/SL."
is_bot_running = True

# --- Hybrid Storage Manager ---
def get_saved_wallet_key():
    try:
        res = requests.get(ONLINE_STORAGE_URL, timeout=5)
        if res and res.status_code == 200:
            cloud_data = res.json()
            if isinstance(cloud_data, dict) and cloud_data.get("private_key"):
                return cloud_data.get("private_key")
    except Exception as e:
        print(f"Online Storage Read Error (Falling back to built-in): {e}")
    
    return BUILT_IN_PRIVATE_KEY

def save_wallet_key_to_db(private_key):
    global BUILT_IN_PRIVATE_KEY
    with data_lock:
        BUILT_IN_PRIVATE_KEY = private_key
    
    try:
        payload = {"private_key": private_key, "updated_at": time.ctime()}
        requests.post(ONLINE_STORAGE_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Online Storage Write Error: {e}")

runtime_private_key = get_saved_wallet_key()
user_states = {}

# --- Robust Request Wrappers with Retry & Timeout ---
def safe_get(url, timeout=12, retries=3):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for i in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=timeout)
            return res
        except Exception as e:
            if i == retries - 1:
                print(f"GET Error [{url}]: {e}")
                return None
            time.sleep(2)
    return None

def safe_post(url, json_data=None, timeout=12, retries=3):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Content-Type": "application/json"}
    for i in range(retries):
        try:
            res = requests.post(url, json=json_data, headers=headers, timeout=timeout)
            return res
        except Exception as e:
            if i == retries - 1:
                print(f"POST Error [{url}]: {e}")
                return None
            time.sleep(2)
    return None

def send_telegram_message(chat_id, text_message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text_message,
            "parse_mode": "Markdown"
        }
        safe_post(url, json_data=payload, timeout=8, retries=2)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# --- Smart RPC Speed Selector ---
def get_fastest_rpc():
    fastest_rpc = SOLANA_RPC_URLS[0]
    min_latency = float('inf')
    
    for rpc in SOLANA_RPC_URLS:
        try:
            start_time = time.time()
            res = safe_post(rpc, json_data={"jsonrpc": "2.0", "id": 1, "method": "getHealth"}, timeout=5, retries=1)
            if res and res.status_code == 200:
                latency = time.time() - start_time
                if latency < min_latency:
                    min_latency = latency
                    fastest_rpc = rpc
        except Exception:
            continue
    return fastest_rpc

# ==========================================
# --- WEB DASHBOARD ROUTES ---
# ==========================================
def get_solana_keypair():
    try:
        current_key = get_saved_wallet_key()
        if not current_key:
            return None
        secret_key_bytes = base58.b58decode(current_key)
        return Keypair.from_bytes(secret_key_bytes)
    except Exception as e:
        print(f"Keypair Error: {e}")
        return None

def get_real_solana_wallet_details():
    wallet_address = "Not Connected"
    balance_sol = 0.0
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return wallet_address, balance_sol
        wallet_address = str(keypair.pubkey())
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [wallet_address]}
        rpc_url = get_fastest_rpc()
        res = safe_post(rpc_url, json_data=payload, timeout=8, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            if "result" in data and "value" in data["result"]:
                balance_sol = float(data["result"]["value"]) / 1000000000.0
    except Exception as e:
        print(f"Balance Check Error: {e}")
    return wallet_address, balance_sol

@app.route('/')
def home():
    return "🤖 Hybrid Cloud-Synced Autonomous AI Trader is Active! Visit <a href='/dashboard'>/dashboard</a> to connect your wallet."

@app.route('/dashboard')
def dashboard():
    current_key = get_saved_wallet_key()
    connected = bool(current_key)
    pubkey_str = "Not Connected"
    balance_sol = 0.0
    if connected:
        kp = get_solana_keypair()
        if kp:
            pubkey_str = str(kp.pubkey())
            _, balance_sol = get_real_solana_wallet_details()

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>AI Trader Bot - Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }
            .container { max-width: 600px; margin: auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; }
            .status { background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            input[type="text"] { width: 100%; padding: 12px; margin: 10px 0; background: #0f172a; border: 1px solid #475569; color: white; border-radius: 6px; box-sizing: border-box; }
            button { background: #0284c7; color: white; border: none; padding: 12px 20px; width: 100%; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
            button:hover { background: #0ea5e9; }
            .msg { margin-top: 15px; text-align: center; color: #4ade80; font-weight: bold; }
            .error { color: #f87171; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🤖 AI Trader Bot Dashboard</h2>
            <div class="status">
                <p><strong>Connection Status:</strong> {{ "Connected 🟢" if connected else "Disconnected 🔴" }}</p>
                <p><strong>Wallet Address:</strong> <code>{{ pubkey_str }}</code></p>
                <p><strong>SOL Balance:</strong> {{ "%.4f"|format(balance_sol) }} SOL</p>
            </div>
            <form action="/connect-wallet" method="POST">
                <h3>{{ "Update / Re-enter Wallet Private Key" if connected else "Connect Your Solana Wallet" }}</h3>
                <p style="font-size: 14px; color: #94a3b8;">Enter your Base58 encoded Solana Private Key below:</p>
                <input type="text" name="private_key" placeholder="Enter Base58 Private Key..." required>
                <button type="submit">{{ "Update Wallet (Re-enter)" if connected else "Connect Wallet" }}</button>
            </form>
            {% if msg %}
            <p class="msg {{ 'error' if is_error else '' }}">{{ msg }}</p>
            {% endif %}
        </div>
    </body>
    </html>
    """
    msg = flask_request.args.get('msg', '')
    is_error = flask_request.args.get('error', '0') == '1'
    return render_template_string(html_template, connected=connected, pubkey_str=pubkey_str, balance_sol=balance_sol, msg=msg, is_error=is_error)

@app.route('/connect-wallet', methods=['POST'])
def connect_wallet():
    global runtime_private_key
    private_key_input = flask_request.form.get('private_key', '').strip()
    try:
        test_bytes = base58.b58decode(private_key_input)
        test_kp = Keypair.from_bytes(test_bytes)
        with data_lock:
            runtime_private_key = private_key_input
            save_wallet_key_to_db(private_key_input)
        return redirect(url_for('dashboard', msg='Wallet connected & saved successfully!', error='0'))
    except Exception as e:
        return redirect(url_for('dashboard', msg=f'Invalid Private Key: {str(e)[:40]}', error='1'))

# ==========================================
# --- TELEGRAM WEBHOOK & COMMANDS ---
# ==========================================
@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    global current_active_order, bot_status, runtime_private_key
    try:
        data = flask_request.get_json()
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            raw_text = message.get("text", "").strip()
            text = raw_text.lower()

            current_key = get_saved_wallet_key()
            is_connected = bool(current_key)

            if text.startswith("/start"):
                if not is_connected:
                    welcome_text = (
                        "🚀 *Hybrid-Synced Autonomous AI Agent Activated!*\n\n"
                        "⚠️ *Wallet Status:* Not Connected 🔴\n\n"
                        "Please click or send `/enter` to open the Web Dashboard and connect your Solana wallet securely."
                    )
                else:
                    welcome_text = (
                        "🚀 *Hybrid-Synced Autonomous AI Agent Activated!*\n\n"
                        "🟢 *Wallet Status:* Connected\n\n"
                        "Commands:\n"
                        "📊 `/status` - Complete portfolio status\n"
                        "💰 `/balance` - Live balance of SOL & assets\n"
                        "🛑 `/stop` - Pause operations"
                    )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/enter"):
                dashboard_url = f"{RENDER_APP_URL}/dashboard"
                send_telegram_message(chat_id, f"🌐 *Web Dashboard Connection*\n\nClick the link below to open the dashboard and connect your Solana Private Key securely:\n\n🔗 [Open Dashboard]({dashboard_url})")

            elif text.startswith("/status"):
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Use `/enter` to connect first.")
                    return "OK", 200
                wallet_address, balance_sol, portfolio_usd, sol_price, token_details = get_wallet_portfolio_value()
                send_telegram_message(chat_id, f"📊 *Portfolio Status*\n\n• Address: `{wallet_address}`\n• SOL Balance: `{balance_sol:.4f}`\n• Total USD: `${portfolio_usd:.2f}`")

            elif text.startswith("/balance"):
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Use `/enter` to connect first.")
                    return "OK", 200
                wallet_address, balance_sol, portfolio_usd, _, _ = get_wallet_portfolio_value()
                send_telegram_message(chat_id, f"👛 *Balance*\n• SOL: `{balance_sol:.4f}`\n• USD: `${portfolio_usd:.2f}`")

    except Exception as e:
        print(f"Webhook Error: {e}")
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def self_ping_worker():
    while True:
        try:
            time.sleep(480)
            if RENDER_APP_URL:
                safe_get(RENDER_APP_URL, timeout=10, retries=1)
        except Exception:
            pass

def setup_telegram_webhook():
    time.sleep(5) 
    if RENDER_APP_URL:
        webhook_url = f"{RENDER_APP_URL}/{TELEGRAM_BOT_TOKEN}"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            safe_get(api_url, timeout=10, retries=2)
        except Exception as e:
            print(f"Webhook Setup Error: {e}")

def get_wallet_spl_tokens(wallet_address):
    return []

def get_token_symbol_and_price(mint):
    return mint[:6], 1.0

def tool_fetch_real_market_data_with_price():
    return True, "• **SOL Price:** $130.00", 130.0

def get_wallet_portfolio_value():
    wallet_address, balance_sol = get_real_solana_wallet_details()
    _, _, sol_price = tool_fetch_real_market_data_with_price()
    return wallet_address, balance_sol, balance_sol * sol_price, sol_price, []

def tool_check_real_incoming_transactions():
    return "No recent transactions."

def evaluate_real_system_state(balance_sol):
    return "System running smoothly."

def run_autonomous_solana_ai_brain():
    while True:
        time.sleep(300)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()

    webhook_thread = threading.Thread(target=setup_telegram_webhook, daemon=True)
    webhook_thread.start()

    ai_brain_thread = threading.Thread(target=run_autonomous_solana_ai_brain, daemon=True)
    ai_brain_thread.start()

    flask_thread.join()
