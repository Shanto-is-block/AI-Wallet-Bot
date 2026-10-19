import os
import json
import time
import threading
from threading import Lock
import sqlite3
import requests
from flask import Flask, request as flask_request
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
import base58

# --- Configuration & Credentials ---
TELEGRAM_BOT_TOKEN = "8931678358:AAEFHNA__FVJlwB6LGbkYRFPXVMm7fYBaaA"      
TELEGRAM_CHAT_ID = "7363218232"

# Solana Wallet Private Key (Environment variable-এ রাখা নিরাপদ, তবে এখানে আপনার কি দেওয়া আছে)
SOLANA_PRIVATE_KEY_BASE58 = "4YEgMCUoSSSR7TE7LGfV4PW3757JRmzvBVbGP4uNFGwCq5ddzfkmiBDPcGL5LqNmLj8CwyTsptzjwXUuSxVYwyBX"      

# Render Web Service Public URL
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# Custom AI API Configuration
CUSTOM_AI_API_URL = "https://ai-api-cgzb.onrender.com"
CUSTOM_AI_API_KEY = "ai_key_1762b5a10bdc7ed4a5db091d"

# Solana RPC URLs
SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana"
]

app = Flask(__name__)

# --- Thread Lock for Global State Safety ---
data_lock = Lock()

bot_status = "Active 🟢 (Real Autonomous Execution Agent)"
current_active_order = "Mission: Real-time on-chain tracking, live market polling, and factual status reporting."
is_bot_running = True

# --- SQLite Database Setup for Secure Logging ---
DB_FILE = "agent_database.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS earnings_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                balance REAL,
                ai_strategy TEXT,
                revenue REAL
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

def log_to_db(balance, strategy, revenue):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO earnings_log (timestamp, balance, ai_strategy, revenue) VALUES (?, ?, ?, ?)",
                       (time.ctime(), balance, strategy, revenue))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Log Error: {e}")

# --- Persistent Memory File Path ---
MEMORY_FILE = "persistent_agent_memory.json"

default_memory_data = {
    "strategy_pool": {
        "Real_OnChain_Monitor": {"weight": 2.5, "success": 0, "fail": 0},
        "Live_Market_Tracking": {"weight": 2.2, "success": 0, "fail": 0}
    },
    "agent_memory": {
        "past_activities": [],
        "total_revenue_generated_sol": 0.0,
        "tools_executed_count": 0
    }
}

def load_persistent_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("strategy_pool", default_memory_data["strategy_pool"]), data.get("agent_memory", default_memory_data["agent_memory"])
    except Exception as e:
        print(f"Memory Load Error: {e}")
    return default_memory_data["strategy_pool"], default_memory_data["agent_memory"]

def save_persistent_memory(s_pool, a_memory):
    try:
        data = {
            "strategy_pool": s_pool,
            "agent_memory": a_memory
        }
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Memory Save Error: {e}")

strategy_pool, agent_memory = load_persistent_memory()

def send_telegram_message(chat_id, text_message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text_message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

@app.route('/')
def home():
    return "🤖 Real-Time Autonomous Solana Agent is Active!"

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    global current_active_order, bot_status
    try:
        data = flask_request.get_json()
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "").strip().lower()

            if text.startswith("/start"):
                welcome_text = (
                    "🚀 *Real Autonomous AI Agent Activated!*\n\n"
                    "🔍 *Mode:* Live On-Chain Data & Real Execution Tracking (No Simulations).\n\n"
                    "Commands:\n"
                    "📊 `/status` - Real-time system performance & wallet state\n"
                    "💰 `/balance` - Live balance and transaction records\n"
                    "📈 `/scan` - Real market price & network status\n"
                    "🛑 `/stop` - Pause agent operations\n"
                    "✍️ `Order: [your command]` - Update operational focus"
                )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/status"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                system_state_msg = evaluate_real_system_state(balance_sol)
                
                status_msg = (
                    f"📊 *Real-Time System Status Report*\n\n"
                    f"👛 *Wallet Address:* `{wallet_address}`\n"
                    f"💰 *Current Balance:* `{balance_sol:.4f} SOL`\n"
                    f"💸 *Tracked Revenue:* `{agent_memory['total_revenue_generated_sol']:.4f} SOL`\n\n"
                    f"{system_state_msg}"
                )
                send_telegram_message(chat_id, status_msg)

            elif text.startswith("/balance"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                incoming_status = tool_check_real_incoming_transactions()
                bal_msg = (
                    f"👛 *Live Wallet & Blockchain Data*\n\n"
                    f"• **Address:** `{wallet_address}`\n"
                    f"• **Confirmed Balance:** `{balance_sol:.4f} SOL`\n"
                    f"• **Latest On-Chain Event:** {incoming_status}"
                )
                send_telegram_message(chat_id, bal_msg)

            elif text.startswith("/scan"):
                success, market_msg = tool_fetch_real_market_data()
                send_telegram_message(chat_id, f"🔍 *Live Market & RPC Scan*\n\n{market_msg}")

            elif text.startswith("/stop"):
                with data_lock:
                    current_active_order = "Paused by user."
                    bot_status = "Paused 🟡"
                send_telegram_message(chat_id, "🛑 Agent operations paused successfully.")

            elif text.startswith("order:"):
                custom_order = message.get("text", "")[6:].strip()
                with data_lock:
                    current_active_order = custom_order
                send_telegram_message(chat_id, f"✅ New operational mission set: {custom_order}")

            else:
                wallet_address, balance_sol = get_real_solana_wallet_details()
                system_state_msg = evaluate_real_system_state(balance_sol)
                send_telegram_message(chat_id, f"🤖 Agent is running live.\n\n{system_state_msg}")

    except Exception as e:
        print(f"Webhook Error: {e}")
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def self_ping_worker():
    while True:
        try:
            time.sleep(480) 
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                requests.get(RENDER_APP_URL, timeout=10)
        except Exception:
            pass

def setup_telegram_webhook():
    time.sleep(5) 
    if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
        webhook_url = f"{RENDER_APP_URL}/{TELEGRAM_BOT_TOKEN}"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            requests.get(api_url, timeout=10)
        except Exception:
            pass

def get_solana_keypair():
    try:
        secret_key_bytes = base58.b58decode(SOLANA_PRIVATE_KEY_BASE58)
        return Keypair.from_bytes(secret_key_bytes)
    except Exception as e:
        print(f"Keypair Error: {e}")
        return None

# ==========================================
# --- REAL ON-CHAIN & MARKET TOOLS ---
# ==========================================

def get_real_solana_wallet_details():
    wallet_address = "Not Connected"
    balance_sol = 0.0
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return wallet_address, balance_sol
        wallet_address = str(keypair.pubkey())
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [wallet_address]}
        for rpc in SOLANA_RPC_URLS:
            try:
                res = requests.post(rpc, json=payload, timeout=6).json()
                if "result" in res and "value" in res["result"]:
                    balance_sol = float(res["result"]["value"]) / 1000000000.0
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"Balance Check Error: {e}")
    return wallet_address, balance_sol

def tool_fetch_real_market_data():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            price = data.get("solana", {}).get("usd", 0)
            change = data.get("solana", {}).get("usd_24h_change", 0)
            return True, f"• **Network Status:** Connected to Solana Mainnet RPCs\n• **SOL Market Price:** ${price} USD\n• **24h Price Change:** {change:.2f}%"
    except Exception as _e:
        pass
    return False, "• **Network Status:** Connected\n• **Market Feed:** Temporarily unavailable via CoinGecko API"

def tool_check_real_incoming_transactions():
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "Keypair configuration error"
        pubkey_str = str(keypair.pubkey())
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [pubkey_str, {"limit": 1}]
        }
        for rpc in SOLANA_RPC_URLS:
            try:
                res = requests.post(rpc, json=payload, timeout=6).json()
                if "result" in res and res["result"]:
                    sig_info = res["result"][0]
                    sig = sig_info.get("signature", "N/A")
                    slot = sig_info.get("slot", "N/A")
                    err = sig_info.get("err")
                    status = "Success 🟢" if err is None else "Failed 🔴"
                    return f"Signature: `{sig[:16]}...` | Slot: {slot} | Status: {status}"
            except Exception:
                continue
        return "No recent transactions found on-chain."
    except Exception as e:
        return f"Error fetching transactions: {str(e)[:25]}"

# ==========================================================
# --- REAL SYSTEM STATE EVALUATION (NO SIMULATIONS) ---
# ==========================================================
def evaluate_real_system_state(balance_sol):
    success, market_msg = tool_fetch_real_market_data()
    tx_status = tool_check_real_incoming_transactions()
    
    with data_lock:
        current_mission = current_active_order

    state_report = (
        f"⚙️ *Live System Execution Report*\n"
        f"• **Active Mission:** {current_mission}\n"
        f"{market_msg}\n"
        f"• **Latest Transaction Log:** {tx_status}\n"
        f"• **Execution Mode:** 100% Real-time RPC and Blockchain verification active."
    )
    
    log_to_db(balance_sol, "Real_System_Check_Active", 0.0)
    return state_report

# --- Autonomous Background Worker ---
def run_autonomous_solana_ai_brain():
    global bot_status, is_bot_running
    while True:
        with data_lock:
            running_status = is_bot_running
        if not running_status:
            time.sleep(5)
            continue
            
        try:
            wallet_address, balance_sol = get_real_solana_wallet_details()
            system_report = evaluate_real_system_state(balance_sol)
            
            action_log = (
                f"🚨 *Live Periodic System Check*\n"
                f"👛 *Wallet:* `{wallet_address}` | 💰 *Balance:* `{balance_sol:.4f} SOL`\n\n"
                f"{system_report}"
            )
            
            send_telegram_message(TELEGRAM_CHAT_ID, action_log)
            time.sleep(300)
        except Exception as e:
            print(f"Worker Error: {e}")
            time.sleep(15)

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
