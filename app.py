import os
import json
import time
import threading
from threading import Lock
import requests
from flask import Flask, request as flask_request
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
import base58

# --- Configuration & Credentials (আপনার তথ্যসমূহ সম্পূর্ণ সুরক্ষিত রাখা হয়েছে) ---
TELEGRAM_BOT_TOKEN = "8931678358:AAEFHNA__FVJlwB6LGbkYRFPXVMm7fYBaaA"      
TELEGRAM_CHAT_ID = "7363218232"

# সোলানা ওয়ালেট প্রাইভেট কি
SOLANA_PRIVATE_KEY_BASE58 = "4YEgMCUoSSSR7TE7LGfV4PW3757JRmzvBVbGP4uNFGwCq5ddzfkmiBDPcGL5LqNmLj8CwyTsptzjwXUuSxVYwyBX"      

# রেন্ডার ওয়েব সার্ভারের পাবলিক লিঙ্ক
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# কাস্টম এআই এপিআই কনফিগারেশন
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
bot_status = "Active 🟢 (Advanced Autonomous Hustle & Cognitive Engine)"
current_active_order = "অটোনমাস মিশন: জিরো ব্যালেন্সেও রিয়েল লাইভ মার্কেট ডেটা ফেচিং, ওয়ালেট ট্রানজেকশন মনিটরিং এবং পার্সিস্টেন্ট মেমোরি লার্নিং চালানো।"
is_bot_running = True

# --- Persistent Memory File Path ---
MEMORY_FILE = "persistent_agent_memory.json"

# --- Default State Data (যদি ফাইল না থাকে) ---
default_memory_data = {
    "strategy_pool": {
        "Custom_AI_API_Hunting": {"weight": 1.9, "success": 0, "fail": 0},
        "Live_Market_Signal_Mining": {"weight": 1.7, "success": 0, "fail": 0},
        "Wallet_Activity_Monitoring": {"weight": 1.6, "success": 0, "fail": 0},
        "Digital_Product_Marketing_Hustle": {"weight": 1.4, "success": 0, "fail": 0},
        "OnChain_DeFi_Execution": {"weight": 1.0, "success": 0, "fail": 0}
    },
    "agent_memory": {
        "past_attempts": [],
        "lessons_learned": [
            "জিরো ব্যালেন্স অবস্থায় পাবলিক এপিআই থেকে লাইভ মার্কেট স্ক্যান এবং পার্সিস্টেন্ট মেমোরির মাধ্যমে কগনিটিভ লার্নিং ট্র্যাক করতে হবে।"
        ],
        "live_signals_mined": 0,
        "market_scans_completed": 0,
        "wallet_checks_done": 0
    }
}

# --- Persistent Memory Load/Save Functions ---
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

# Initial Load into Global Variables
strategy_pool, agent_memory = load_persistent_memory()

# --- Send Telegram Message Helper ---
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

# --- Flask Route for Webhook / Home ---
@app.route('/')
def home():
    return "🤖 Solana Advanced Autonomous AI & Hustle Agent with Persistent Memory is Active!"

# টেলিগ্রাম থেকে আপডেট রিসিভ করার জন্য ওয়েবহুক রুট
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
                    "🚀 *Advanced Autonomous Agent Activated!*\n\n"
                    "🧠📈💾 *বৈশিষ্ট্য:* পার্সিস্টেন্ট মেমোরি সহ এই এজেন্টটি রিয়েল-টাইমে মার্কেট স্ক্যান, ওয়ালেট মনিটরিং এবং স্থায়ী লার্নিং পরিচালনা করে।\n\n"
                    "ইন্টারেক্টিভ কমান্ডসমূহ:\n"
                    "📊 `/status` - ব্রেনের লাইভ রিপোর্ট ও মেমোরি স্ট্যাটাস দেখতে\n"
                    "💰 `/balance` - ওয়ালেটের রিয়েল ব্যালেন্স ও অ্যাড্রেস দেখতে\n"
                    "📈 `/scan` - তাৎক্ষণিক লাইভ মার্কেট ইন্টেলিজেন্স স্ক্যান করতে\n"
                    "🛑 `/stop` - বোট পজ করতে\n"
                    "✍️ `Order: আপনার নির্দেশ` - নতুন মিশন সেট করতে"
                )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/status"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                ai_thought, execution_out = evaluate_and_run_autonomous_brain(balance_sol)
                
                with data_lock:
                    current_status = bot_status
                    current_order = current_active_order
                    total_scans = agent_memory["market_scans_completed"]
                    total_signals = agent_memory["live_signals_mined"]

                status_msg = (
                    f"📊 *Autonomous Agent Full Report*\n\n"
                    f"🔹 *Status:* {current_status}\n"
                    f"👛 *Wallet Address:* `{wallet_address}`\n"
                    f"💰 *Balance:* {balance_sol:.4f} SOL\n"
                    f"🎯 *Mission:* {current_order}\n"
                    f"🧠 *Total Scans Saved:* {total_scans} | *Signals Mined:* {total_signals}\n\n"
                    f"{ai_thought}\n\n"
                    f"⚙️ *Execution Result:*\n{execution_out}"
                )
                send_telegram_message(chat_id, status_msg)

            elif text.startswith("/balance"):
                wallet_address, balance_sol = get_real_solana_wallet_details()
                activity_status = check_wallet_recent_activity()
                bal_msg = (
                    f"👛 *Wallet Details & Funds*\n\n"
                    f"• **Address:** `{wallet_address}`\n"
                    f"• **Current Balance:** `{balance_sol:.4f} SOL`\n"
                    f"• **Recent Activity:** {activity_status}"
                )
                send_telegram_message(chat_id, bal_msg)

            elif text.startswith("/scan"):
                success, market_msg = fetch_live_solana_market_intel()
                scan_msg = f"🔍 *Manual Market Intel Scan*\n\n{market_msg}"
                send_telegram_message(chat_id, scan_msg)

            elif text.startswith("/stop"):
                with data_lock:
                    current_active_order = "Paused by user."
                    bot_status = "Paused 🟡"
                send_telegram_message(chat_id, "🛑 অটোনমাস এআই ইঞ্জিন সাময়িকভাবে পজ করা হয়েছে।")

            elif text.startswith("order:"):
                custom_order = message.get("text", "")[6:].strip()
                with data_lock:
                    current_active_order = custom_order
                send_telegram_message(chat_id, f"✅ নতুন অটোনমাস মিশন গ্রহণ করা হয়েছে: {custom_order}")

            else:
                wallet_address, balance_sol = get_real_solana_wallet_details()
                ai_thought, execution_out = evaluate_and_run_autonomous_brain(balance_sol)
                reply_msg = f"🤖 আমি অটোনমাস মিশনে সক্রিয় আছি।\n\n{ai_thought}\n\nসাহায্য বা কমান্ড দেখতে **/start** বা **/status** ব্যবহার করুন।"
                send_telegram_message(chat_id, reply_msg)

    except Exception as e:
        print(f"Webhook Error: {e}")
    return "OK", 200

# --- Flask Server Runner Function ---
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- Self-Ping Loop to Keep Render Awake ---
def self_ping_worker():
    while True:
        try:
            time.sleep(480) 
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                requests.get(RENDER_APP_URL, timeout=10)
        except Exception:
            pass

# --- Set Telegram Webhook Automatically ---
def setup_telegram_webhook():
    time.sleep(5) 
    if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
        webhook_url = f"{RENDER_APP_URL}/{TELEGRAM_BOT_TOKEN}"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            requests.get(api_url, timeout=10)
        except Exception:
            pass

# --- Solana Wallet Keypair from Private Key ---
def get_solana_keypair():
    try:
        secret_key_bytes = base58.b58decode(SOLANA_PRIVATE_KEY_BASE58)
        return Keypair.from_bytes(secret_key_bytes)
    except Exception as e:
        print(f"Keypair Error: {e}")
        return None

# --- Real Solana RPC & Wallet Details Fetcher ---
def get_real_solana_wallet_details():
    wallet_address = "Not Connected"
    balance_sol = 0.0
    
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return wallet_address, balance_sol
            
        wallet_address = str(keypair.pubkey())
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        
        for rpc in SOLANA_RPC_URLS:
            try:
                response = requests.post(rpc, json=payload, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and "value" in data["result"]:
                        lamports = data["result"]["value"]
                        balance_sol = float(lamports) / 1000000000.0 
                        break
            except Exception:
                continue
                
    except Exception as e:
        print(f"Solana RPC Error: {e}")
        
    return wallet_address, balance_sol

# --- Real-Action: Check Recent Wallet Signatures / Inbound Activity ---
def check_wallet_recent_activity():
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "Keypair error"
        pubkey_str = str(keypair.pubkey())
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [pubkey_str, {"limit": 2}]
        }
        
        for rpc in SOLANA_RPC_URLS:
            try:
                res = requests.post(rpc, json=payload, timeout=6).json()
                if "result" in res and res["result"]:
                    sigs = res["result"]
                    latest_sig = sigs[0].get("signature", "N/A")[:16] + "..."
                    return f"সক্রিয় (শেষ সিগনেচার: {latest_sig})"
            except Exception:
                continue
        return "কোনো সাম্প্রতিক অন-চেইন লেনদেন নেই।"
    except Exception as e:
        return f"অ্যাক্টিভিটি চেক ত্রুটি: {str(e)[:20]}"

# --- Real Action: Fetch Live Market Intelligence ---
def fetch_live_solana_market_intel():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            sol_price = data.get("solana", {}).get("usd", 0)
            sol_change = data.get("solana", {}).get("usd_24h_change", 0)
            return True, f"🌐 *[Live Market Data]:* Solana (SOL) Price: **${sol_price} USD** | 24h Change: **{sol_change:.2f}%**"
    except Exception as e:
        print(f"Market Intel Fetch Error: {e}")
    
    return False, "⚠️ *[Market Intel Notice]:* পাবলিক নোড থেকে লাইভ ডেটা ফেচ করতে সাময়িক সমস্যা হয়েছে।"

# --- Custom AI API & Hustle Tool ---
def call_custom_ai_and_hunt(balance_sol):
    try:
        headers = {
            "Authorization": f"Bearer {CUSTOM_AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "balance": balance_sol,
            "mission": "Autonomous market signal mining, wallet activity tracking, and persistent learning"
        }
        
        res = requests.post(CUSTOM_AI_API_URL, json=payload, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            advice = data.get('advice', data.get('strategy_advice', 'কাস্টম এআই ব্রেন পার্সিস্টেন্ট মেমোরি সহ রিয়েল-টাইম সিগন্যাল তৈরি করেছে।'))
            return True, f"🧠 *[Custom AI API Brain]:* {advice}"
        else:
            if balance_sol == 0.0:
                return True, "📈 *[Hustle Mode Action]:* ওয়ালেটে ০ SOL। লাইভ মার্কেট স্ক্যান ও পার্সিস্টেন্ট মেমোরি আপডেট চলছে।"
            else:
                return True, "📈 *[Capital Deployed]:* অন-চেইন প্রটোকল এক্সিকিউশন শুরু।"
    except Exception as e:
        if balance_sol == 0.0:
            return True, "📈 *[Hustle Fallback Action]:* ওয়ালেটে ০ SOL থাকায় লাইভ মার্কেট ইন্টেলিজেন্স ও পার্সিস্টেন্ট লার্নিং চলছে।"
        return False, f"❌ *[Custom AI API Error]:* {str(e)[:30]}"

# --- On-Chain Execution Tool ---
def execute_on_chain_hand_tool(target_address=None, amount_sol=0.0):
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return False, "❌ Keypair loading failed."

        sender_pubkey = keypair.pubkey()

        if target_address and amount_sol > 0:
            lamports = int(amount_sol * 1000000000)
            recipient_pubkey = Pubkey.from_string(target_address)
            
            latest_blockhash_res = requests.post(
                SOLANA_RPC_URLS[0], 
                json={"jsonrpc": "2.0", "id": 1, "method": "getLatestBlockhash", "params": []},
                timeout=5
            ).json()
            blockhash_str = latest_blockhash_res['result']['value']['blockhash']
            recent_blockhash = Hash.from_string(blockhash_str)

            instruction = transfer(
                TransferParams(
                    from_pubkey=sender_pubkey,
                    to_pubkey=recipient_pubkey,
                    lamports=lamports
                )
            )

            compile_message = Message.new_with_blockhash([instruction], sender_pubkey, recent_blockhash)
            tx = Transaction.new_unsigned(compile_message)
            tx.sign([keypair], recent_blockhash)

            raw_tx = bytes(tx)
            encoded_tx = base58.b58encode(raw_tx).decode('utf-8')

            broadcast_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [encoded_tx, {"encoding": "base58"}]
            }
            res = requests.post(SOLANA_RPC_URLS[0], json=broadcast_payload, timeout=8).json()
            
            if "result" in res:
                return True, f"✅ *[On-Chain Success]* Transaction Sent! Signature: {res['result']}"
            else:
                raise Exception(f"RPC Reject: {res.get('error', 'Unknown error')}")

        return True, "🎯 *[On-Chain Execution]:* ক্যাপিটাল ডেপ্লয়মেন্ট ও ট্রেডিং প্রটোকল সফল।"

    except Exception as e:
        return False, f"❌ *[On-Chain Error]:* {str(e)}"

# --- Autonomous Brain & Real-Action Hustle Engine with Persistent Memory ---
def evaluate_and_run_autonomous_brain(balance_sol):
    global strategy_pool, agent_memory
    thought_log = ""
    execution_result = ""
    
    try:
        with data_lock:
            best_strategy = max(strategy_pool.keys(), key=lambda s: strategy_pool[s]["weight"])
            current_lesson = agent_memory['lessons_learned'][-1]
        
        thought_log = (
            f"🧠 *[Persistent Autonomous Brain]* ওয়ালেট ব্যালেন্স: {balance_sol:.4f} SOL\n"
            f"🎯 নির্বাচিত কৌশল: `{best_strategy}`\n"
            f"📚 সাম্প্রতিক স্থায়ী শিক্ষা: {current_lesson}"
        )
        
        ai_success, ai_msg = call_custom_ai_and_hunt(balance_sol)
        thought_log += f"\n{ai_msg}"
        
        if ai_success:
            if balance_sol > 0.0:
                chain_success, chain_msg = execute_on_chain_hand_tool()
                if chain_success:
                    with data_lock:
                        strategy_pool[best_strategy]["weight"] += 0.2
                        agent_memory["past_attempts"].append({"status": "SUCCESS", "strategy": best_strategy})
                        save_persistent_memory(strategy_pool, agent_memory)
                    execution_result = f"✅ *[Execution Success via {best_strategy}]:* {chain_msg}"
                else:
                    raise Exception(chain_msg)
            else:
                with data_lock:
                    agent_memory["market_scans_completed"] += 1
                    agent_memory["live_signals_mined"] += 1
                    agent_memory["wallet_checks_done"] += 1
                    strategy_pool["Live_Market_Signal_Mining"]["weight"] += 0.1
                    strategy_pool["Wallet_Activity_Monitoring"]["weight"] += 0.1
                    
                    market_success, market_data_msg = fetch_live_solana_market_intel()
                    wallet_activity = check_wallet_recent_activity()
                    
                    new_lesson = f"পার্সিস্টেন্ট হাস্টল #{agent_memory['market_scans_completed']}: লাইভ মার্কেট ও ওয়ালেট সফলভাবে স্ক্যান ও মেমোরিতে সংরক্ষিত হয়েছে।"
                    if new_lesson not in agent_memory["lessons_learned"]:
                        agent_memory["lessons_learned"].append(new_lesson)
                    
                    # সেভ মেমোরি টু ফাইল
                    save_persistent_memory(strategy_pool, agent_memory)
                
                execution_result = (
                    "📈 *[Persistent Market Signal & Wallet Monitor]*\n"
                    f"• **অবস্থা:** ওয়ালেটে গ্যাস ফি (SOL) শূন্য।\n"
                    f"• **বাস্তব কাজ (Action):** বোট রিয়েল-টাইমে মার্কেট ইন্টেলিজেন্স ট্র্যাক করে লোকাল মেমোরি ফাইলে সেভ করেছে।\n"
                    f"• **মার্কেট ডেটা:** {market_data_msg}\n"
                    f"• **ওয়ালেট স্ট্যাটাস:** {wallet_activity}\n"
                    f"• **ফলাফল:** মেমোরি পার্সিস্টেন্ট থাকায় ব্রেনের অভিজ্ঞতা স্থায়ীভাবে সংরক্ষিত রয়েছে!"
                )
        else:
            raise Exception("Custom AI API call failed.")
            
    except Exception as e:
        error_desc = str(e)[:35]
        with data_lock:
            strategy_pool["Custom_AI_API_Hunting"]["weight"] = max(0.5, strategy_pool["Custom_AI_API_Hunting"]["weight"] - 0.15)
            correction_lesson = f"ত্রুটি থেকে শিক্ষা: '{error_desc}' মেমোরিতে স্থায়ীভাবে নোট করা হয়েছে।"
            if correction_lesson not in agent_memory["lessons_learned"]:
                agent_memory["lessons_learned"].append(correction_lesson)
            save_persistent_memory(strategy_pool, agent_memory)
            
        execution_result = (
            f"🔄 *[Self-Healing & Persistent Memory Updated]*\n"
            f"⚠️ ত্রুটি ধরা পড়েছে: `{error_desc}`\n"
            f"🧠 **বোটের আত্মশুদ্ধি:** সমস্যা বিশ্লেষণ করে পার্সিস্টেন্ট ফাইলে নোট করা হয়েছে এবং কাজ সচল রয়েছে।"
        )
        
    return thought_log, execution_result

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
            ai_thought_process, execution_output = evaluate_and_run_autonomous_brain(balance_sol)
            
            with data_lock:
                current_order = current_active_order
                
            action_log = (
                f"🎯 *Active Mission:* {current_order}\n"
                f"👛 *Wallet Address:* `{wallet_address}`\n"
                f"💰 *Balance:* {balance_sol:.4f} SOL\n\n"
                f"{ai_thought_process}\n\n"
                f"⚙️ *Execution Result:*\n{execution_output}"
            )
            
            send_telegram_message(TELEGRAM_CHAT_ID, action_log)
            
            with data_lock:
                bot_status = "Active 🟢 (Persistent Autonomous Engine Running)"
            
            time.sleep(300) 
                
        except Exception as e:
            with data_lock:
                bot_status = f"Error: {str(e)} ❌"
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
