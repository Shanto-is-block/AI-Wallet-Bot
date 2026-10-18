import os
import time
import threading
import requests
from web3 import Web3
from google import genai
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --- Configuration (আপনি চাইলে Render Environment Variable থেকেও এগুলো নিতে পারেন) ---
TELEGRAM_BOT_TOKEN = "8974206752:AAFqOusGoMFjh0snVhUQZFEvt58jJ56FVIk"      # আপনার টেলিগ্রাম বট টোকেন দিন
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"              # আপনার জেমিনি এআই কি দিন
WALLET_PRIVATE_KEY = "0x5dacb82768813d1099cba7032498179aeac894604dba7c2d4766f503b8188527"      # আপনার ওয়ালেট প্রাইভেট কি দিন
RPC_URL = "https://rpc-amoy.polygon.technology/"      # নেটওয়ার্ক RPC URL

# Flask App to keep Render alive via Web Service pings
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 AI Telegram Crypto Bot is Alive and Running 24/7!"

# Global state for bot tracking
bot_status = "Inactive 🔴"
last_ai_decision = "No decision yet."

# --- AI & Web3 Autonomous Worker ---
def run_crypto_ai_brain(chat_id, app_context):
    global bot_status, last_ai_decision
    bot_status = "Active 🟢"
    
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.is_connected():
            bot_status = "Error: RPC Connection Failed ❌"
            return

        account = w3.eth.account.from_key(WALLET_PRIVATE_KEY)
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        while True:
            # Check balance
            balance_wei = w3.eth.get_balance(account.address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            
            # AI Brain Decision making
            prompt = f"Analyze current micro-task environment for automated web3 execution. Wallet Balance: {balance_eth} MATIC. Give a short, strategic action plan to grow assets."
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            last_ai_decision = response.text.strip()
            
            # Construct Telegram update message
            msg = (
                f"🤖 **AI Bot Update**\n\n"
                f"💰 **Balance:** {balance_eth} MATIC\n"
                f"🧠 **AI Strategy:** {last_ai_decision}"
            )
            
            # Send message to user via Telegram API
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
            
            # Wait for 10 minutes before next cycle
            time.sleep(600)
            
    except Exception as e:
        bot_status = f"Error: {str(e)} ❌"

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    welcome_text = (
        "👋 স্বাগতম! এটি আপনার পার্সোনাল **AI Autonomous Crypto Bot**।\n\n"
        "নিচের কমান্ডগুলো ব্যবহার করুন:\n"
        "🚀 `/runbot` - এআই ও ক্রিপ্টো বট ব্যাকগ্রাউন্ডে চালু করতে\n"
        "📊 `/status` - বটের বর্তমান অবস্থা ও ব্যালেন্স জানতে\n"
        "🛑 `/stop` - বট বন্ধ করতে"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def runbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    global bot_status
    if "Active" in bot_status:
        await update.message.reply_text("⚠️ বট ইতিমধ্যে ব্যাকগ্রাউন্ডে চালু আছে!")
    else:
        await update.message.reply_text("🚀 এআই ক্রিপ্টো বট ব্যাকগ্রাউন্ডে চালু করা হচ্ছে...")
        # Start background worker thread
        t = threading.Thread(target=run_crypto_ai_brain, args=(chat_id, context), daemon=True)
        t.start()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        f"📊 **Bot Status Report**\n\n"
        f"🔹 **Status:** {bot_status}\n"
        f"🧠 **Last AI Insight:** {last_ai_decision}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

# --- Run Flask Server in Background (For Render Keep-Alive) ---
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    # Start Flask web server thread so Render keeps the service awake
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start Telegram Bot Polling
    app_telegram = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("runbot", runbot_command))
    app_telegram.add_handler(CommandHandler("status", status_command))
    
    print("🤖 Telegram Bot is polling for updates...")
    app_telegram.run_polling()
