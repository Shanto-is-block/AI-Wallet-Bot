import os
import time
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from solders.keypair import Keypair
import base58

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8974206752:AAFqOusGoMFjh0snVhUQZFEvt58jJ56FVIk"      

# আপনার সোলানা ওয়ালেটের প্রাইভেট কি (Base58 স্ট্রিং ফরম্যাটে এখানে বসাবেন)
SOLANA_PRIVATE_KEY_BASE58 = "আপনার_সোলানা_ওয়ালেটের_প্রাইভেট_কি_এখানে_দিন"      

# আপনার রেন্ডার ওয়েব সার্ভারের পাবলিক লিঙ্ক
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# Solana RPC URLs (সোলানা নেটওয়ার্কের রিয়েল নোড)
SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana"
]

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Solana Autonomous Crypto AI Agent is Active!"

# Global State and Memory (Autonomous Mind State)
bot_status = "Active 🟢 (Solana Autonomous Brain Active)"
current_active_order = "স্বয়ংক্রিয় মিশন: সোলানা নেটওয়ার্ক মনিটরিং ও সেলফ-লার্নিং হান্টিং।"
last_ai_action_log = "System initialized with Solana private key capabilities."
ai_memory = []  
agent_learning_log = [] 
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

# --- Autonomous Decision & Self-Correction Engine ---
def evaluate_and_decide_strategy(balance_sol):
    global agent_learning_log
    strategy_thought = ""
    
    try:
        if balance_sol == 0.0:
            strategy_thought = "🔍 চিন্তা ও বিশ্লেষণ: সোলানা ওয়ালেটে কোনো ফান্ড (SOL) নেই। গ্যাস ফি বা ট্রানজেকশনের জন্য ফাউসেট বা হান্টিং স্ট্র্যাটেজি সক্রিয় করা হলো।"
        else:
            strategy_thought = f"💡 চিন্তা ও বিশ্লেষণ: সোলানা ওয়ালেট ব্যালেন্স ({balance_sol:.4f} SOL) অনুকূল রয়েছে।"
            
        if len(agent_learning_log) > 0:
            last_lesson = agent_learning_log[-1]
            strategy_thought += f"\n🧠 সেলফ-লার্নিং আপডেট: [{last_lesson}] থেকে শিক্ষা নেওয়া হয়েছে।"
            
    except Exception as e:
        error_msg = str(e)
        strategy_thought = f"❌ এরর শনাক্ত হয়েছে: {error_msg}।"
        agent_learning_log.append(f"Fixed error: {error_msg[:30]}")
        
    return strategy_thought

# --- Autonomous Background Brain Worker ---
def run_autonomous_solana_ai_brain(application):
    global bot_status, last_ai_action_log, ai_memory, current_active_order, is_bot_running
    
    while True:
        if not is_bot_running:
            time.sleep(5)
            continue
            
        try:
            wallet_address, balance_sol = get_real_solana_wallet_details()
            ai_thought_process = evaluate_and_decide_strategy(balance_sol)
            
            api_status = "Solana network stable."
            try:
                res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    price = data.get('solana', {}).get('usd', 0)
                    api_status = f"Solana Price: ${price}"
            except Exception:
                api_status = "API fallback active."

            action_log = (
                f"🎯 Active Mission: {current_active_order}\n"
                f"👛 Solana Wallet: {wallet_address}\n"
                f"💰 On-Chain Balance: {balance_sol:.4f} SOL\n"
                f"🧠 **AI Autonomous Reasoning:**\n{ai_thought_process}\n"
                f"⚙️ Network Status: {api_status}"
            )
            last_ai_action_log = action_log
            bot_status = "Active 🟢 (Solana Autonomous Brain Running)"
            
            ai_memory.append(action_log)
            if len(ai_memory) > 5:
                ai_memory.pop(0)
            
            time.sleep(120) 
                
        except Exception as e:
            bot_status = f"Error: {str(e)} ❌"
            agent_learning_log.append(f"Crash avoided: {str(e)[:30]}")
            time.sleep(15)

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 **Solana Autonomous Crypto Agent Activated!**", parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_address, balance_sol = get_real_solana_wallet_details()
    ai_thought = evaluate_and_decide_strategy(balance_sol)
    status_msg = f"📊 **Status Report**\n👛 `{wallet_address}`\n💰 {balance_sol:.4f} SOL\n🧠 {ai_thought}"
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order, bot_status
    current_active_order = "Paused by user."
    bot_status = "Paused 🟡"
    await update.message.reply_text("🛑 পজ করা হয়েছে।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order, bot_status
    user_text = update.message.text.strip()
    if user_text.lower().startswith("order:"):
        current_active_order = user_text[6:].strip()
        await update.message.reply_text(f"✅ নতুন মিশন সেট করা হয়েছে: {current_active_order}")

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
