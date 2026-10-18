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
RPC_URL = "https://rpc-mainnet.maticvigil.com"      

# Flask App to keep Render alive via Web Service pings
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 AI Telegram Crypto Bot with Memory is Alive and Running 24/7!"

# Global state and Memory for bot tracking
bot_status = "Inactive 🔴"
last_ai_decision = "No decision yet."
ai_memory = []  # এআই-এর পূর্বের সিদ্ধান্তগুলো মনে রাখার জন্য মেমরি লিস্ট

# --- AI & Web3 Autonomous Worker with Memory ---
def run_crypto_ai_brain(chat_id, app_context):
    global bot_status, last_ai_decision, ai_memory
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
            
            # আগের মেমরি বা হিস্ট্রি প্রম্পটের সাথে যুক্ত করা যাতে এআই কনটেক্সট মনে রাখতে পারে
            history_context = "\n".join(ai_memory[-5:]) if ai_memory else "No prior history."
            
            # AI Brain Decision making with Memory Context
            prompt = (
                f"You are an advanced automated Web3 trading strategist. "
                f"Wallet Balance: {balance_eth} MATIC.\n"
                f"Previous AI Decisions History:\n{history_context}\n\n"
                f"Analyze the current micro-task environment and give a short, strategic action plan to grow assets, considering what was decided before."
            )
            
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt
            )
            
            last_ai_decision = response.text.strip()
            
            # নতুন সিদ্ধান্তটি মেমরিতে যোগ করা (সর্বোচ্চ শেষ ৫টি মনে রাখবে)
            ai_memory.append(last_ai_decision)
            if len(ai_memory) > 5:
                ai_memory.pop(0)
            
            # Construct Telegram update message
            msg = (
                f"🤖 **AI Bot Update (With Memory)**\n\n"
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
        "👋 স্বাগতম! এটি আপনার পার্সোনাল **AI Autonomous Crypto Bot (Memory Enabled)**।\n\n"
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
        await update.message.reply_text("🚀 এআই ক্রিপ্টো বট মেমরি সিস্টেমসহ ব্যাকগ্রাউন্ডে চালু করা হচ্ছে...")
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
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    app_telegram = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("runbot", runbot_command))
    app_telegram.add_handler(CommandHandler("status", status_command))
    
    print("🤖 Telegram Bot with Memory is polling for updates...")
    app_telegram.run_polling()
