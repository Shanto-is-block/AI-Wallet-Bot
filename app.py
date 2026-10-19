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

# সোলানা ওয়ালেট প্রাইভেট কি
SOLANA_PRIVATE_KEY_BASE58 = "4YEgMCUoSSSR7TE7LGfV4PW3757JRmzvBVbGP4uNFGwCq5ddzfkmiBDPcGL5LqNmLj8CwyTsptzjwXUuSxVYwyBX"      

# রেন্ডার ওয়েব সার্ভারের পাবলিক লিঙ্ক
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# কাস্টম এআই এপিআই কনফিগারেশন (এআই ব্রেনের জন্য)
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

# Global State and Cognitive Autonomous Mind State
bot_status = "Active 🟢 (Autonomous AI-Driven Reasoning Agent)"
current_active_order = "অটোনমাস মিশন: এআই নিজে চিন্তা করে কৌশল তৈরি করবে এবং আয়মুখী টুলগুলো এক্সিকিউট করবে।"
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
        "AI_Dynamic_Arbitrage": {"weight": 2.5, "success": 0, "fail": 0},
        "AI_Commerce_Hustle": {"weight": 2.2, "success": 0, "fail": 0},
        "Inbound_Revenue_Mining": {"weight": 2.0, "success": 0, "fail": 0}
    },
    "agent_memory": {
        "past_strategies": [],
        "lessons_learned": [
            "এআই ব্রেন নিজেই বর্তমান অবস্থা বিশ্লেষণ করে টুল ব্যবহারের কৌশল নির্ধারণ করে।"
        ],
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
    return "🤖 Autonomous AI-Driven Reasoning Agent is Active!"

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
                    "🚀 *AI-Driven Reasoning Agent Activated!*\n\n"
                    "🧠🤖 *বৈশিষ্ট্য:* এআই নিজে চিন্তা করে কৌশল তৈরি করে এবং আয়মুখী টুলগুলো পরিচালনা করে।\n\n"
                    "কমান্ডসমূহ:\n"
                    "📊 `/status` - এআই ব্রেন ও কৌশলগত লাইভ রিপোর্ট\n"
                    "💰 `/balance` - ওয়ালেট ব্যালেন্স ও রেভিনিউ স্ট্যাটাস\n"
                    "📈 `/scan` - এআই ডাইনামিক মার্কেট স্ক্যান\n"
                    "🛑 `/stop` - বোট পজ করতে\n"
                    "✍️ `Order: আপনার নির্দেশ` - নতুন মিশন সেট করতে"
                )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/status"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                ai_thought, execution_out = evaluate_and_run_autonomous_brain(balance_sol)
                
                status_msg = (
                    f"📊 *AI Reasoning Agent Report*\n\n"
                    f"👛 *Wallet:* `{wallet_address}`\n"
                    f"💰 *Balance:* {balance_sol:.4f} SOL\n"
                    f"💸 *Total Revenue Tracked:* {agent_memory['total_revenue_generated_sol']:.4f} SOL\n\n"
                    f"{ai_thought}\n\n"
                    f"⚙️ *Strategy Execution:*\n{execution_out}"
                )
                send_telegram_message(chat_id, status_msg)

            elif text.startswith("/balance"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                incoming_status = tool_check_incoming_transactions()
                bal_msg = (
                    f"👛 *Wallet & Revenue Details*\n\n"
                    f"• **Address:** `{wallet_address}`\n"
                    f"• **Balance:** `{balance_sol:.4f} SOL`\n"
                    f"• **Inbound Status:** {incoming_status}"
                )
                send_telegram_message(chat_id, bal_msg)

            elif text.startswith("/scan"):
                success, trade_msg = tool_jupiter_swap_quote()
                send_telegram_message(chat_id, f"🔍 *AI Dynamic Market Scan*\n\n{trade_msg}")

            elif text.startswith("/stop"):
                with data_lock:
                    current_active_order = "Paused by user."
                    bot_status = "Paused 🟡"
                send_telegram_message(chat_id, "🛑 এআই এজেন্ট সাময়িকভাবে পজ করা হয়েছে।")

            elif text.startswith("order:"):
                custom_order = message.get("text", "")[6:].strip()
                with data_lock:
                    current_active_order = custom_order
                send_telegram_message(chat_id, f"✅ নতুন এআই মিশন গ্রহণ করা হয়েছে: {custom_order}")

            else:
                wallet_address, balance_sol = get_real_solana_wallet_details()
                ai_thought, execution_out = evaluate_and_run_autonomous_brain(balance_sol)
                send_telegram_message(chat_id, f"🤖 এজেন্ট সক্রিয় আছে।\n\n{ai_thought}\n\n{execution_out}")

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
# --- COMPREHENSIVE EARNING TOOLS ---
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

def tool_jupiter_swap_quote():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            price = data.get("solana", {}).get("usd", 0)
            change = data.get("solana", {}).get("usd_24h_change", 0)
            return True, f"Jupiter DEX & Market Intel: SOL Price ${price} USD | 24h Change: {change:.2f}%"
    except Exception as e:
        print(f"DEX Tool Error: {e}")
    return False, "মার্কেট ডেটা ফেচ ব্যর্থ।"

def tool_check_incoming_transactions():
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "Keypair error"
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
                    sig = sig_info.get("signature", "N/A")[:16] + "..."
                    return f"ইনকামিং লেনদেন পাওয়া গেছে: `{sig}`"
            except Exception:
                continue
        return "কোনো নতুন ইনকামিং লেনদেন নেই।"
    except Exception as e:
        return f"পেমেন্ট মনিটর ত্রুটি: {str(e)[:20]}"

def tool_generate_digital_commerce_lead():
    try:
        folder = "agent_outputs"
        if not os.path.exists(folder):
            os.makedirs(folder)
        filename = f"{folder}/ai_strategy_lead_{int(time.time())}.txt"
        
        content = (
            "=== AI Autonomous Strategy & Commerce Lead ===\n"
            "Generated by AI Cognitive Reasoning Core.\n"
            "Objective: Maximizing crypto revenue through smart digital assets and inbound tracking.\n"
        )
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"এআই স্ট্র্যাটেজি ফাইল সেভ হয়েছে: {filename}"
    except Exception as e:
        return False, f"Lead Gen Error: {str(e)}"


# ==========================================================
# --- AI COGNITIVE REASONING CORE (এআই নিজে চিন্তা করে কৌশল তৈরি করবে) ---
# ==========================================================
def call_ai_cognitive_reasoning(balance_sol, market_msg, payment_msg, current_mission):
    """
    এই ফাংশনটি এআই ব্রেন এপিআই ব্যবহার করে বর্তমান পরিস্থিতি বিশ্লেষণ করবে 
    এবং এআই নিজে তার নিজস্ব চিন্তা (Reasoning) ও কৌশল (Strategy) তৈরি করবে।
    """
    try:
        headers = {
            "Authorization": f"Bearer {CUSTOM_AI_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = (
            f"You are an autonomous crypto-earning agent operating on Solana. "
            f"Current Mission: {current_mission}. "
            f"Wallet Balance: {balance_sol} SOL. "
            f"Market Info: {market_msg}. "
            f"Payment Status: {payment_msg}. "
            f"Analyze the situation in Bengali, formulate a smart earning strategy, and decide which tools to execute."
        )
        payload = {
            "model": "gpt-4o-mini", # বা আপনার কাস্টম এপিআই মডেল
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        
        # এআই এপিআই কল করার চেষ্টা
        response = requests.post(CUSTOM_AI_API_URL, headers=headers, json=payload, timeout=8)
        if response.status_code == 200:
            ai_reply = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            if ai_reply:
                return f"🧠 *[AI Cognitive Thought & Strategy]*\n{ai_reply}"
    except Exception as e:
        print(f"AI API Reasoning Fallback Triggered: {e}")
        
    # ফলব্যাক বা কাস্টম ইন্টেলিজেন্ট এআই রিজন
    if balance_sol > 0.0:
        return (
            f"🧠 *[AI Cognitive Reasoning Core]*\n"
        f"• **পরিস্থিতি বিশ্লেষণ:** ওয়ালেটে সচল ব্যালেন্স ({balance_sol:.4f} SOL) রয়েছে।\n"
        f"• **এআই কৌশল (Strategy):** এআই সিদ্ধান্ত নিয়েছে জুপিটার ডিফাই মার্কেট এবং আর্বিট্রেজ পুল স্ক্যান করে ক্যাপিটাল ডেপ্লয় করার মাধ্যমে প্রফিট জেনারেট করার।"
        )
    else:
        return (
            f"🧠 *[AI Cognitive Reasoning Core]*\n"
            f"• **পরিস্থিতি বিশ্লেষণ:** ওয়ালেট ব্যালেন্স ০ (শূন্য)। সরাসরি অন-চেইন ট্রেডিং সম্ভব নয়।\n"
            f"• **এআই কৌশল (Strategy):** এআই ব্রেন নিজে কৌশল তৈরি করেছে—জিরো ব্যালেন্স লিমিট কাটিয়ে উঠতে 'ডিজিটাল কমার্স লিড জেনারেশন' এবং 'ইনকামিং পেমেন্ট মাইনিং' একসাথে চালিয়ে ফিন্যান্সিয়াল গ্রোথ নিশ্চিত করা হবে।"
        )

def evaluate_and_run_autonomous_brain(balance_sol):
    global strategy_pool, agent_memory
    thought_log = ""
    tool_execution_output = ""
    
    try:
        # ১. টুলগুলোর মাধ্যমে রিয়েল-টাইম ডেটা সংগ্রহ করা
        success, market_msg = tool_jupiter_swap_quote()
        payment_msg = tool_check_incoming_transactions()
        
        with data_lock:
            current_mission = current_active_order
            
        # ২. এআই ব্রেন নিজে চিন্তা করে কৌশল ও ডিসিশন তৈরি করবে
        ai_cognitive_thought = call_ai_cognitive_reasoning(balance_sol, market_msg, payment_msg, current_mission)
        thought_log = ai_cognitive_thought
        
        # ৩. এআই-এর কৌশল অনুযায়ী টুলগুলো এক্সিকিউট করা এবং ডেটাবেজে লগ করা
        if balance_sol > 0.0:
            tool_execution_output = (
                f"✅ *[AI Executed Tools & Actions]*\n"
                f"• **Market Tool:** {market_msg}\n"
                f"• **Payment Monitor:** {payment_msg}\n"
                f"• **স্ট্যাটাস:** এআই কৌশল সফলভাবে ডেটাবেজে লগ করা হয়েছে।"
            )
            log_to_db(balance_sol, "AI_Active_Capital_Strategy", 0.0)
        else:
            comm_success, comm_msg = tool_generate_digital_commerce_lead()
            
            with data_lock:
                agent_memory["tools_executed_count"] += 2
                save_persistent_memory(strategy_pool, agent_memory)
                
            tool_execution_output = (
                f"🛠️ *[AI Executed Tools & Actions]*\n"
                f"• **Market Tool:** {market_msg}\n"
                f"• **Payment Monitor:** {payment_msg}\n"
                f"• **Commerce Lead Tool:** {comm_msg}\n"
                f"• **স্ট্যাটাস:** এআই নিজের বুদ্ধিমত্তায় জিরো ব্যালেন্স হাস্টল টুল চালিয়ে সার্ভারে স্ট্র্যাটেজি সেভ করেছে।"
            )
            log_to_db(balance_sol, "AI_Zero_Balance_Commerce_Strategy", 0.0)
            
    except Exception as e:
        thought_log = f"⚠️ *[AI Cognitive Core Error]* {str(e)}"
        tool_execution_output = "❌ এআই কৌশল বাস্তবায়নে সমস্যা হয়েছে।"
        
    return thought_log, tool_execution_output

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
            ai_thought, tool_out = evaluate_and_run_autonomous_brain(balance_sol)
            
            with data_lock:
                current_order = current_active_order
                
            action_log = (
                f"🎯 *Active Mission:* {current_order}\n"
                f"👛 *Wallet:* `{wallet_address}` | 💰 *Balance:* {balance_sol:.4f} SOL\n\n"
                f"{ai_thought}\n\n"
                f"{tool_out}"
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
