import os
import time
import threading
import requests
import json
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.message import Message
import base58

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8974206752:AAFqOusGoMFjh0snVhUQZFEvt58jJ56FVIk"      
SOLANA_PRIVATE_KEY_BASE58 = "4YEgMCUoSSSR7TE7LGfV4PW3757JRmzvBVbGP4uNFGwCq5ddzfkmiBDPcGL5LqNmLj8CwyTsptzjwXUuSxVYwyBX"      
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# 👉 এখানে আপনার যত খুশি ফ্রি জেমিনি এপিআই কি লিস্ট আকারে বসাতে পারেন।
# যদি কোনো কি না থাকে বা ফাঁকা রাখেন (""), তবে সিস্টেম নিজে থেকেই ফলব্যাক মোডে কাজ করবে।
GEMINI_API_KEYS = [
    "AQ.Ab8RN6IbYudc3aFEJ7rsG8MbfZbdZkmvOYP1h-vBBkdhut4Wag",
    "AQ.Ab8RN6JIdSFm3ryeqLsmZ74wsYnncsRFX302mXF4ZPbCJ_xMPQ",
    "YOUR_THIRD_GEMINI_API_KEY"
]

current_key_index = 0

SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana"
]

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Multi-Key Gemini AI Solana Autonomous Agent is Active!"

# Global State
bot_status = "Active 🟢 (Multi-Key Rotation & Smart Fallback Engine Running)"
current_active_order = "অটোনমাস মিশন: মাল্টি-এপিআই জেমিনি ব্রেনের মাধ্যমে রিয়েল মার্কেট স্ক্যান, ডিসিশন মেকিং এবং প্রফিট প্ল্যান তৈরি।"
last_ai_action_log = "System initialized."
ai_memory = []  
is_bot_running = True

# --- Self-Ping Loop to Keep Render Awake ---
def self_ping_worker():
    while True:
        try:
            time.sleep(480) 
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                requests.get(RENDER_APP_URL, timeout=10)
        except Exception:
            pass

# --- Solana Wallet Keypair ---
def get_solana_keypair():
    try:
        secret_key_bytes = base58.b58decode(SOLANA_PRIVATE_KEY_BASE58)
        return Keypair.from_bytes(secret_key_bytes)
    except Exception as e:
        print(f"Keypair Error: {e}")
        return None

# --- TOOL 1: Get Wallet Details ---
def get_wallet_details():
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "Not Connected", 0.0
        wallet_address = str(keypair.pubkey())
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [wallet_address]}
        
        for rpc in SOLANA_RPC_URLS:
            try:
                response = requests.post(rpc, json=payload, timeout=6)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and "value" in data["result"]:
                        lamports = data["result"]["value"]
                        return wallet_address, float(lamports) / 1000000000.0
            except Exception:
                continue
        return wallet_address, 0.0
    except Exception:
        return "Error", 0.0

# --- TOOL 2: Fetch Market Trends (Dexscreener) ---
def fetch_market_trends():
    try:
        url = "https://api.dexscreener.com/latest/dex/tokens/solana"
        res = requests.get(url, timeout=6)
        if res.status_code == 200:
            data = res.json()
            pairs = data.get('pairs', [])
            if pairs:
                top = pairs[0]
                name = top.get('baseToken', {}).get('name', 'Unknown')
                symbol = top.get('baseToken', {}).get('symbol', 'UNK')
                price = top.get('priceUsd', '0')
                change = top.get('priceChange', {}).get('h6', 0)
                return f"Top Trending Token: {name} ({symbol}) | Price: ${price} | 6h Change: {change}%"
        return "Market data unavailable."
    except Exception as e:
        return f"Market fetch error: {str(e)[:25]}"

# --- TOOL 3: On-Chain Guardrail Execution (Safety Limited) ---
def execute_on_chain_transfer(target_address, amount_sol):
    if amount_sol > 0.05:
        return "❌ [Safety Guardrail Blocked]: সুরক্ষার স্বার্থে ০.০৫ SOL এর বেশি স্বয়ংক্রিয় ট্রান্সফার নিষিদ্ধ।"
    
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "❌ Keypair error."
            
        lamports = int(amount_sol * 1000000000)
        recipient_pubkey = Pubkey.from_string(target_address)
        
        latest_blockhash_res = requests.post(
            SOLANA_RPC_URLS[0], 
            json={"jsonrpc": "2.0", "id": 1, "method": "getLatestBlockhash", "params": []},
            timeout=5
        ).json()
        blockhash_str = latest_blockhash_res['result']['value']['blockhash']
        from solders.hash import Hash
        recent_blockhash = Hash.from_string(blockhash_str)

        instruction = transfer(TransferParams(from_pubkey=keypair.pubkey(), to_pubkey=recipient_pubkey, lamports=lamports))
        compile_message = Message.new_with_blockhash([instruction], keypair.pubkey(), recent_blockhash)
        tx = Transaction.new_unsigned(compile_message)
        tx.sign([keypair], recent_blockhash)

        raw_tx = bytes(tx)
        encoded_tx = base58.b58encode(raw_tx).decode('utf-8')

        broadcast_payload = {"jsonrpc": "2.0", "id": 1, "method": "sendTransaction", "params": [encoded_tx, {"encoding": "base58"}]}
        res = requests.post(SOLANA_RPC_URLS[0], json=broadcast_payload, timeout=8).json()
        
        if "result" in res:
            return f"✅ [On-Chain Success] Tx Signature: {res['result']}"
        else:
            return f"❌ RPC Error: {res.get('error', 'Unknown')}"
    except Exception as e:
        return f"❌ Execution Exception: {str(e)}"

# --- Smart Internal AI Brain (এপিআই না থাকলেও কাজ করবে) ---
def rule_based_fallback_brain(balance_sol, market_info):
    advice = ""
    if balance_sol == 0.0:
        advice = "💡 ওয়ালেটে ০ SOL রয়েছে। গ্যাস ফি যুক্ত না করা পর্যন্ত অন-চেইন ট্রেড স্থগিত রাখা নিরাপদ। তবে রিয়েল মার্কেট স্ক্যান ও সিগন্যাল হান্টিং চালু আছে।"
    else:
        advice = f"🚀 ওয়ালেটে পর্যাপ্ত ফান্ড ({balance_sol} SOL) রয়েছে। ট্রেন্ডিং টোকেন সোয়াপ বা হোল্ড করার জন্য অনুকূল পরিবেশ।"
        
    return (
        f"🧠 **[Smart Built-in AI Brain Active]:**\n"
        f"📊 **Market Report:** {market_info}\n"
        f"👛 **Wallet Balance:** {balance_sol} SOL\n"
        f"💡 **Strategic Advice:** {advice}\n"
        f"*(নোট: এপিআই কি সংযুক্ত না থাকায় বা লিমি트 শেষ হওয়ায় ইন্টারনাল স্মার্ট এআই ইঞ্জিন এই ডিসিশন নিয়েছে)*"
    )

# --- Multi-Key Rotation Gemini Brain with Seamless Fallback ---
def ask_gemini_ai_agent(wallet_address, balance_sol, market_info, user_order):
    global current_key_index
    
    # যদি কোনো ভ্যালিড এপিআই কি না থাকে, তবে সরাসরি ইন্টারনাল ব্রেনে চলে যাবে
    valid_keys = [k for k in GEMINI_API_KEYS if k and "YOUR_" not in k]
    if not valid_keys:
        return rule_based_fallback_brain(balance_sol, market_info)

    prompt = f"""
    You are an autonomous crypto AI agent managing a Solana wallet.
    Current Mission: {user_order}
    Wallet Address: {wallet_address}
    Wallet Balance: {balance_sol} SOL
    Market Info: {market_info}
    
    Analyze the situation using ReAct (Thought -> Plan -> Action format) in Bengali.
    Provide smart insights, whether to hold, hunt tokens, or wait for gas fee if balance is 0. Keep it professional and strategic.
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    total_keys = len(valid_keys)
    
    # লুপ চালিয়ে এক এক করে কি (Key) ট্রাই করা হবে
    for _ in range(total_keys):
        active_key = valid_keys[current_key_index % total_keys]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={active_key}"
        
        try:
            response = requests.post(url, json=payload, timeout=8)
            
            # যদি এপিআই লিমিট শেষ হয় (429) বা অন্য কোনো কোটা এরর আসে, পরের কি-তে সুইচ করবে
            if response.status_code == 429 or response.status_code == 403:
                current_key_index = (current_key_index + 1) % total_keys
                continue
                
            if response.status_code == 200:
                res_json = response.json()
                candidate = res_json.get('candidates', [])
                if candidate:
                    text_output = candidate[0]['content']['parts'][0]['text']
                    return f"🧠 **[Gemini AI Active Brain (Key #{current_key_index + 1})]:**\n{text_output}"
            
            current_key_index = (current_key_index + 1) % total_keys
            
        except Exception:
            current_key_index = (current_key_index + 1) % total_keys
            continue

    # যদি সবকটি কি-এর লিমিটই শেষ হয়ে যায়, তবে সিস্টেম ক্র্যাশ না করে স্মার্ট ইন্টারনাল ব্রেনে সুইচ করবে
    print("⚠️ All Gemini API keys exhausted. Falling back to Smart Built-in AI Brain.")
    return rule_based_fallback_brain(balance_sol, market_info)

# --- Autonomous Background Worker Loop ---
def run_autonomous_solana_ai_brain(application):
    global bot_status, last_ai_action_log, ai_memory, current_active_order, is_bot_running
    
    while True:
        if not is_bot_running:
            time.sleep(5)
            continue
            
        try:
            wallet_address, balance_sol = get_wallet_details()
            market_info = fetch_market_trends()
            
            ai_thought_process = ask_gemini_ai_agent(wallet_address, balance_sol, market_info, current_active_order)

            action_log = (
                f"🎯 **Mission:** {current_active_order}\n"
                f"👛 **Wallet:** `{wallet_address}`\n"
                f"💰 **Balance:** {balance_sol:.4f} SOL\n\n"
                f"{ai_thought_process}"
            )
            last_ai_action_log = action_log
            bot_status = "Active 🟢 (Multi-Key Rotation & Smart Engine Healthy)"
            
            ai_memory.append(action_log)
            if len(ai_memory) > 5:
                ai_memory.pop(0)
            
            time.sleep(120) 
                
        except Exception as e:
            bot_status = f"Error: {str(e)[:30]} ❌ (Self-Healing Active)"
            time.sleep(15)

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Multi-Key Gemini AI Autonomous Solana Agent Activated!**\n\n"
        "🔒 আপনার প্রাইভেট কি নিরাপদ। বোটটি এখন একাধিক এপিআই কি রোটেশন এবং স্মার্ট ফলব্যাক ইঞ্জিন নিয়ে সচল রয়েছে।\n\n"
        "কমান্ডসমূহ:\n"
        "📊 `/status` - এআই অ্যানালাইসিস ও মার্কেট রিপোর্ট দেখতে\n"
        "🛑 `/stop` - বোট পজ করতে",
        parse_mode="Markdown"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_address, balance_sol = get_wallet_details()
    market_info = fetch_market_trends()
    ai_thought = ask_gemini_ai_agent(wallet_address, balance_sol, market_info, current_active_order)
    
    status_msg = (
        f"📊 **AI Agent Live Status Report**\n\n"
        f"🔹 **Status:** {bot_status}\n"
        f"👛 **Wallet:** `{wallet_address}`\n"
        f"💰 **Balance:** {balance_sol:.4f} SOL\n"
        f"🎯 **Mission:** {current_active_order}\n\n"
        f"{ai_thought}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order, bot_status
    current_active_order = "Paused by user. Use 'Order:' to resume."
    bot_status = "Paused 🟡"
    await update.message.reply_text("🛑 অটোনমাস ইঞ্জিন সাময়িকভাবে পজ করা হয়েছে।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order
    user_text = update.message.text.strip()
    
    if user_text.lower().startswith("order:"):
        current_active_order = user_text[6:].strip()
        await update.message.reply_text(f"✅ নতুন এআই মিশন সেট করা হয়েছে: {current_active_order}")
    else:
        wallet_address, balance_sol = get_wallet_details()
        market_info = fetch_market_trends()
        ai_thought = ask_gemini_ai_agent(wallet_address, balance_sol, market_info, current_active_order)
        await update.message.reply_text(
            f"🤖 এআই এজেন্ট আপনার বার্তা বিশ্লেষণ করেছে:\n\n{ai_thought}\n\nনতুন নির্দেশ দিতে **'Order:'** লিখে পাঠান।"
        )

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()

    app_telegram = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("status", status_command))
    app_telegram.add_handler(CommandHandler("stop", stop_command))
    app_telegram.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    ai_brain_thread = threading.Thread(target=run_autonomous_solana_ai_brain, args=(app_telegram,), daemon=True)
    ai_brain_thread.start()

    app_telegram.run_polling()
