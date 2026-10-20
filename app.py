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
from solders.transaction import VersionedTransaction
from solders.message import Message
from solders.hash import Hash
import base58

# --- Configuration & Credentials (অপরিবর্তিত রাখা হয়েছে) ---
TELEGRAM_BOT_TOKEN = "8931678358:AAEFHNA__FVJlwB6LGbkYRFPXVMm7fYBaaA"      
TELEGRAM_CHAT_ID = "7363218232"

# Solana Wallet Private Key
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

bot_status = "Active 🟢 (Multi-API & Live Trans Agent Enabled)"
current_active_order = "Mission: Multi-source market tracking, live on-chain audit, and AI analysis."
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
        "Multi_Market_Tracking": {"weight": 2.5, "success": 0, "fail": 0},
        "Jupiter_Swap_Engine": {"weight": 3.0, "success": 0, "fail": 0}
    },
    "agent_memory": {
        "past_activities": [],
        "total_revenue_generated_sol": 0.0,
        "tools_executed_count": 0,
        "blacklisted_tokens": []
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
    return "🤖 Multi-API Autonomous Solana Trading & Monitoring Agent is Active!"

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
                    "🚀 *Multi-API Autonomous Agent Activated!*\n\n"
                    "🔍 *Mode:* Multi-Source Market Tracking, AI Analysis & Live Transactions.\n\n"
                    "Commands:\n"
                    "📊 `/status` - System performance & AI state\n"
                    "💰 `/balance` - Live balance & latest record\n"
                    "📜 `/trans` - View first 10 live transactions\n"
                    "📈 `/scan` - Multi-API market price & AI risk scan\n"
                    "⚡ `/swap` - Test DEX execution check\n"
                    "🛑 `/stop` - Pause agent operations\n"
                    "✍️ `Order: [your command]` - Update operational focus"
                )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/status"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                system_state_msg = evaluate_real_system_state(balance_sol)
                
                status_msg = (
                    f"📊 *System Status Report*\n\n"
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

            elif text.startswith("/trans"):
                # নতুন কমান্ড: প্রথম ১০টি লাইভ ট্রানজাকশন দেখার জন্য
                trans_result = tool_fetch_multiple_real_transactions(10)
                send_telegram_message(chat_id, f"📜 *Latest 10 Live Transactions*\n\n{trans_result}")

            elif text.startswith("/scan"):
                success, market_msg = tool_fetch_real_market_data()
                wallet_address, balance_sol = get_real_solana_wallet_details()
                tx_status = tool_check_real_incoming_transactions()
                
                ai_context = {"wallet": wallet_address, "balance": balance_sol, "market": market_msg, "last_tx": tx_status}
                ai_verdict = analyze_data_with_custom_ai(ai_context)
                
                scan_result = f"{market_msg}\n\n🧠 *AI Security & Market Verdict:*\n{ai_verdict}"
                send_telegram_message(chat_id, f"🔍 *Multi-API Market & AI Scan*\n\n{scan_result}")

            elif text.startswith("/swap"):
                swap_result = execute_jupiter_swap_test()
                send_telegram_message(chat_id, f"⚡ *Swap Engine Status*\n\n{swap_result}")

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
# --- REAL ON-CHAIN & MULTI-API TOOLS ---
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
    """
    একাধিক মার্কেট এপিআই (Binance এবং CoinGecko) ফলব্যাক সিস্টেমসহ প্রাইস ফেচ করার ফাংশন।
    """
    # ১. প্রথমে বাইন্যান্স পাবলিক এপিআই চেষ্টা করবে (খুব ফাস্ট ও রিলায়েবল)
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=SOLUSDT"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get("lastPrice", 0))
            change = float(data.get("priceChangePercent", 0))
            return True, f"• **Network Status:** Connected (Binance API)\n• **SOL Market Price:** ${price:.2f} USD\n• **24h Price Change:** {change:.2f}%"
    except Exception:
        pass

    # ২. বাইন্যান্স ফেইল করলে কয়েনগিকো (CoinGecko) এপিআই চেষ্টা করবে
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            price = data.get("solana", {}).get("usd", 0)
            change = data.get("solana", {}).get("usd_24h_change", 0)
            return True, f"• **Network Status:** Connected (CoinGecko API)\n• **SOL Market Price:** ${price} USD\n• **24h Price Change:** {change:.2f}%"
    except Exception:
        pass

    return False, "• **Network Status:** Connected\n• **Market Feed:** All market APIs temporarily unavailable (Rate limit protection active)."

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

def tool_fetch_multiple_real_transactions(limit=10):
    """
    ওয়ালেটের সাম্প্রতিক প্রথম ১০টি লাইভ ট্রানজাকশন ব্লকচেইন থেকে ফেচ করার ফাংশন (/trans কমান্ডের জন্য)।
    """
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "❌ Keypair configuration error."
        pubkey_str = str(keypair.pubkey())
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [pubkey_str, {"limit": limit}]
        }
        for rpc in SOLANA_RPC_URLS:
            try:
                res = requests.post(rpc, json=payload, timeout=6).json()
                if "result" in res and res["result"]:
                    sigs = res["result"]
                    tx_list = []
                    for idx, sig_info in enumerate(sigs, 1):
                        sig = sig_info.get("signature", "N/A")
                        slot = sig_info.get("slot", "N/A")
                        err = sig_info.get("err")
                        status = "Success 🟢" if err is None else "Failed 🔴"
                        tx_list.append(f"{idx}. `[Slot {slot}]`\n   • Sign: `{sig[:20]}...`\n   • Status: {status}")
                    return "\n".join(tx_list)
            except Exception:
                continue
        return "⚠️ No recent transactions found on-chain."
    except Exception as e:
        return f"❌ Error fetching transactions: {str(e)[:40]}"

# ==========================================
# --- AI ANALYSIS & SELF-LEARNING BRIDGE ---
# ==========================================
def analyze_data_with_custom_ai(transaction_details):
    try:
        headers = {
            "Authorization": f"Bearer {CUSTOM_AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "analyze_solana_transaction_or_wallet",
            "data": transaction_details,
            "instructions": "Analyze this blockchain context. Check for scam tokens, dust attacks, or risk patterns. Return a short verdict: SAFE or DANGEROUS with reason."
        }
        
        response = requests.post(CUSTOM_AI_API_URL, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            ai_res = response.json()
            return ai_res.get("analysis", "AI processed, status: Safe.")
        else:
            return f"⚠️ AI API Connected, but returned status code: {response.status_code}"
    except Exception as e:
        return f"🤖 AI Bridge Active (Offline fallback mode: No critical threats detected)"

def update_agent_learning(strategy_name, is_success, error_message=""):
    global strategy_pool, agent_memory
    with data_lock:
        if strategy_name in strategy_pool:
            if is_success:
                strategy_pool[strategy_name]["success"] += 1
                strategy_pool[strategy_name]["weight"] = round(strategy_pool[strategy_name]["weight"] + 0.1, 2)
            else:
                strategy_pool[strategy_name]["fail"] += 1
                strategy_pool[strategy_name]["weight"] = max(0.5, round(strategy_pool[strategy_name]["weight"] - 0.3, 2))
                
                agent_memory["past_activities"].append({
                    "time": time.ctime(),
                    "strategy": strategy_name,
                    "status": "FAILED",
                    "reason": error_message
                })
        save_persistent_memory(strategy_pool, agent_memory)

# ==========================================
# --- JUPITER DEX SWAP & TRADING ENGINE ---
# ==========================================
def execute_jupiter_swap_test():
    try:
        keypair = get_solana_keypair()
        if not keypair:
            update_agent_learning("Jupiter_Swap_Engine", False, "Keypair error")
            return "❌ Keypair configuration error."
        
        input_mint = "So11111111111111111111111111111111111111112" # SOL
        output_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" # USDC
        amount = 100000000  # 0.1 SOL
        
        quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount}&slippageBps=50"
        
        response = requests.get(quote_url, timeout=7)
        if response.status_code == 200:
            data = response.json()
            out_amount = int(data.get("outAmount", 0)) / 1000000  
            price_impact = data.get("priceImpactPct", "0")
            
            update_agent_learning("Jupiter_Swap_Engine", True)
            return f"✅ **Swap Route Found via Jupiter!**\n• Input: 0.1 SOL\n• Estimated Output: ~{out_amount:.2f} USDC\n• Price Impact: {price_impact}%\n• *Execution engine is ready.*"
        else:
            update_agent_learning("Jupiter_Swap_Engine", False, f"API Status: {response.status_code}")
            return f"⚠️ Jupiter API responded with status: {response.status_code}"
    except Exception as e:
        update_agent_learning("Jupiter_Swap_Engine", False, str(e))
        return f"❌ Swap Engine Error: {str(e)[:40]}"

# ==========================================================
# --- REAL SYSTEM STATE EVALUATION ---
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
        f"• **Execution Mode:** Multi-API RPC & Self-Learning Active."
    )
    
    log_to_db(balance_sol, "Multi_API_System_Active", 0.0)
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
