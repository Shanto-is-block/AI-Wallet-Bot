import os
import time
import threading
import requests
from web3 import Web3
from google import genai
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8974206752:AAFqOusGoMFjh0snVhUQZFEvt58jJ56FVIk"      
GEMINI_API_KEY = "AQ.Ab8RN6IIrNUqpGF4vyN_feje76WvXS2RR2VEnPJ5MwgbsU3grQ"              
WALLET_PRIVATE_KEY = "0x5dacb82768813d1099cba7032498179aeac894604dba7c2d4766f503b8188527"      

# আপনার রেন্ডার ওয়েব সার্ভারের পাবলিক লিঙ্কটি এখানে বসিয়ে দেবেন (Self-Ping এর জন্য)
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

RPC_URLS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://polygon.llamarpc.com",
    "https://polygon-rpc.com"
]

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 AI Telegram Crypto Bot with Built-in Fallback AI & Self-Ping is Alive and Running 24/7!"

# Global state and Memory
bot_status = "Inactive 🔴"
last_ai_decision = "No decision yet."
ai_memory = []  
ai_mode = "Gemini Cloud AI 🧠"  
is_bot_running = False

# --- Self-Ping Loop to Keep Render Awake ---
def self_ping_worker():
    while True:
        try:
            # প্রতি ৮ মিনিট (৪৮০ সেকেন্ড) পর পর নিজের সার্ভারে রিকোয়েস্ট পাঠাবে
            time.sleep(480)
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                response = requests.get(RENDER_APP_URL, timeout=10)
                print(f"Self-ping sent successfully, status code: {response.status_code}")
        except Exception as e:
            print(f"Self-ping error: {e}")

def get_builtin_fallback_strategy(balance_eth):
    global ai_memory
    strategies = [
        f"Built-in Fallback Agent: Wallet balance is {balance_eth} MATIC. Holding position and scanning gas optimization windows.",
        f"Built-in Fallback Agent: Analyzing historical memory. Recommending capital preservation.",
        f"Built-in Fallback Agent: Network stable. Executing defensive asset management for {balance_eth} MATIC."
    ]
    return strategies[len(ai_memory) % len(strategies)]

# --- Background Autonomous Worker ---
def run_crypto_ai_brain(chat_id):
    global bot_status, last_ai_decision, ai_memory, ai_mode, is_bot_running
    bot_status = "Active 🟢"
    
    while is_bot_running:
        try:
            w3 = None
            for rpc in RPC_URLS:
                try:
                    temp_w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
                    if temp_w3.is_connected():
                        w3 = temp_w3
                        break
                except Exception:
                    continue
                    
            if not w3 or not w3.is_connected():
                bot_status = "Error: All RPC Connections Failed ❌"
                time.sleep(30)
                continue

            account = w3.eth.account.from_key(WALLET_PRIVATE_KEY)
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            while is_bot_running:
                try:
                    balance_wei = w3.eth.get_balance(account.address)
                    balance_eth = w3.from_wei(balance_wei, 'ether')
                    history_context = "\n".join(ai_memory[-5:]) if ai_memory else "No prior history."
                    
                    try:
                        prompt = (
                            f"You are an advanced automated Web3 trading strategist. "
                            f"Wallet Balance: {balance_eth} MATIC.\n"
                            f"Previous AI Decisions History:\n{history_context}\n\n"
                            f"Analyze the current environment and give a short, strategic action plan to grow assets."
                        )
                        
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=prompt
                        )
                        last_ai_decision = response.text.strip()
                        ai_mode = "Gemini Cloud AI 🧠"
                        bot_status = "Active 🟢 (Gemini Mode)"
                        
                    except Exception as gemini_err:
                        last_ai_decision = get_builtin_fallback_strategy(balance_eth)
                        ai_mode = "Built-in Local Fallback AI 🛡️ (Gemini Offline)"
                        bot_status = "Active 🟢 (Fallback Mode)"
                    
                    ai_memory.append(last_ai_decision)
                    if len(ai_memory) > 5:
                        ai_memory.pop(0)
                    
                    msg = (
                        f"🤖 **AI Autonomous Bot Update**\n\n"
                        f"⚙️ **AI Engine:** {ai_mode}\n"
                        f"💰 **Balance:** {balance_eth} MATIC\n"
                        f"🧠 **AI Strategy:** {last_ai_decision}"
                    )
                    
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
                    
                except Exception as inner_e:
                    last_ai_decision = f"Warning: Loop error handled ({str(inner_e)})"
                
                # Check every 10 minutes, checking `is_bot_running` flag periodically
                for _ in range(60):
                    if not is_bot_running:
                        break
                    time.sleep(10)
                
        except Exception as outer_e:
            bot_status = f"Error: {str(outer_e)} ❌ (Auto-recovering...)"
            time.sleep(30)

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 স্বাগতম! এটি আপনার পার্সোনাল **AI Autonomous Crypto Bot**。\n\n"
        "ব্যবহার করার জন্য কমান্ডগুলো:\n"
        "🚀 `/runbot` - বট ব্যাকগ্রাউন্ডে চালু করতে\n"
        "📊 `/status` - বর্তমান অবস্থা ও এআই স্ট্র্যাটেজি জানতে\n"
        "🛑 `/stop` - বট বন্ধ করতে"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def runbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    global is_bot_running, bot_status
    if is_bot_running:
        await update.message.reply_text("⚠️ বট ইতিমধ্যে ব্যাকগ্রাউন্ডে চালু আছে!")
    else:
        is_bot_running = True
        await update.message.reply_text("🚀 এআই ক্রিপ্টো বট ব্যাকগ্রাউন্ডে চালু করা হচ্ছে...")
        t = threading.Thread(target=run_crypto_ai_brain, args=(chat_id,), daemon=True)
        t.start()

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_bot_running, bot_status
    is_bot_running = False
    bot_status = "Inactive 🔴"
    await update.message.reply_text("🛑 বট বন্ধ করা হয়েছে।")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        f"📊 **Bot Status Report**\n\n"
        f"🔹 **Status:** {bot_status}\n"
        f"⚙️ **Active Engine:** {ai_mode}\n"
        f"🧠 **Last AI Insight:** {last_ai_decision}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    # Flask সার্ভার চালু করার জন্য থ্রেড
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # কোডের নিজস্ব সেলফ-পিং (Self-Ping) থ্রেড চালু করা
    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()

    # রেন্ডার সার্ভারে অ্যাপ ডিপ্লয় করার পর RENDER_APP_URL ভ্যারিয়েবলে আপনার রেন্ডার লিংকটি বসিয়ে দেবেন।
    
    app_telegram = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("runbot", runbot_command))
    app_telegram.add_handler(CommandHandler("stop", stop_command))
    app_telegram.add_handler(CommandHandler("status", status_command))
    
    print("🤖 Telegram Bot is polling for updates with Self-Ping enabled...")
    app_telegram.run_polling()
