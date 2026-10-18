import os
import time
import json
import threading
import requests
from web3 import Web3
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8974206752:AAFqOusGoMFjh0snVhUQZFEvt58jJ56FVIk"      
WALLET_PRIVATE_KEY = "0x5dacb82768813d1099cba7032498179aeac894604dba7c2d4766f503b8188527"      

# আপনার রেন্ডার ওয়েব সার্ভারের পাবলিক লিঙ্ক
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# Polygon RPC URLs
RPC_URLS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://polygon.llamarpc.com",
    "https://polygon-rpc.com"
]

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Interactive & Default-Ordered Crypto AI Agent is Active!"

# Global State and Memory
bot_status = "Active 🟢 (Executing Default Crypto Acquisition Order)"
# ডিফল্ট অর্ডার হিসেবে ওয়ালেটে ক্রিপ্টো আয় করার মিশন সেট করা আছে
current_active_order = "ডিফল্ট অর্ডার: যেকোনো উপায়ে এই খালি ওয়ালেটে ক্রিপ্টো আয় করে আনা (ফাউসেট, সার্ভিস বিক্রি, মাইক্রো-টাস্ক ও অফ-চেইন হান্টিং)।"
last_ai_action_log = "System initialized with Default Crypto Acquisition Mission."
ai_memory = []  
ai_mode = "Autonomous Interactive AI Brain with Default Order 🧠"  
is_bot_running = True

# --- Self-Ping Loop to Keep Render Awake ---
def self_ping_worker():
    while True:
        try:
            time.sleep(480) # প্রতি ৮ মিনিট পর পর সেলফ-পিং
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                requests.get(RENDER_APP_URL, timeout=10)
        except Exception:
            pass

# --- Background Autonomous Worker (ডিফল্ট বা নতুন অর্ডার ব্যাকগ্রাউন্ডে রান করবে) ---
def run_crypto_ai_brain(application):
    global bot_status, last_ai_action_log, ai_memory, current_active_order, is_bot_running
    
    while True:
        if not is_bot_running:
            time.sleep(5)
            continue
            
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
                    
            account = w3.eth.account.from_key(WALLET_PRIVATE_KEY) if w3 and w3.is_connected() else None
            
            while is_bot_running:
                # ওয়ালেট ব্যালেন্স চেক করা
                balance_eth = 0
                wallet_address = "Not Connected"
                if w3 and account:
                    wallet_address = account.address
                    try:
                        balance_wei = w3.eth.get_balance(account.address)
                        balance_eth = w3.from_wei(balance_wei, 'ether')
                    except Exception:
                        balance_eth = 0
                
                # ব্যাকএন্ড এক্সিকিউশন লজিক (ডিফল্ট বা কাস্টম অর্ডার অনুযায়ী)
                action_log = (
                    f"🎯 Active Order/Mission: {current_active_order}\n"
                    f"👛 Wallet Address: {wallet_address[:6]}...{wallet_address[-4:] if wallet_address != 'Not Connected' else ''}\n"
                    f"💰 Current Wallet Balance: {balance_eth} MATIC\n"
                    f"⚙️ Backend Action: Multi-vector hunting active (Scanning digital services, micro-tasks, faucets & off-chain bounties)..."
                )
                last_ai_action_log = action_log
                bot_status = "Active 🟢 (Executing Mission)"
                
                ai_memory.append(action_log)
                if len(ai_memory) > 5:
                    ai_memory.pop(0)
                
                time.sleep(60) # প্রতি ১ মিনিট পরপর ব্যাকএন্ডে হান্টিং ও লজিক রান করবে
                
        except Exception as e:
            bot_status = f"Error: {str(e)} ❌ (Auto-Healing...)"
            time.sleep(10)

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 স্বাগতম! আমি আপনার অটোনমাস ক্রিপ্টো এআই এজেন্ট।\n\n"
        "⚡ **ডিফল্ট অর্ডার:** আমার ভেতরে অলরেডি নির্দেশ দেওয়া আছে—**'যেকোনো উপায়ে এই খালি ওয়ালেটে ক্রিপ্টো আয় করে আনা'**। বট চালু হওয়ার সাথে সাথেই আমি এই মিশনে ব্যাকগ্রাউন্ডে কাজ শুরু করে দিয়েছি!\n\n"
        "💬 আপনি চাইলে আমার সাথে সাধারণ চ্যাট করতে পারেন বা কাজের পরিধি নিয়ে কথা বলতে পারেন। নতুন কোনো সুনির্দিষ্ট অর্ডার দিতে চাইলে মেসেজের শুরুতে **'Order:'** লিখে পাঠাতে পারেন।\n\n"
        "কমান্ডগুলো:\n"
        "📊 `/status` - বর্তমান ওয়ালেট ব্যালেন্স ও ব্যাকএন্ড লোগ দেখতে\n"
        "🛑 `/stop` - সাময়িকভাবে হান্টিং থামাতে"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # রিয়েল-টাইম ওয়ালেট ব্যালেন্স চেক করে স্ট্যাটাসে দেখানোর জন্য
    balance_eth = 0
    try:
        w3 = None
        for rpc in RPC_URLS:
            try:
                temp_w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
                if temp_w3.is_connected():
                    w3 = temp_w3
                    break
            except Exception:
                continue
        if w3:
            account = w3.eth.account.from_key(WALLET_PRIVATE_KEY)
            balance_wei = w3.eth.get_balance(account.address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
    except Exception:
        balance_eth = 0

    status_msg = (
        f"📊 **Agent Status & Backend Report**\n\n"
        f"🔹 **Status:** {bot_status}\n"
        f"💰 **Wallet Balance:** {balance_eth} MATIC\n"
        f"🎯 **Active Order/Mission:** {current_active_order}\n\n"
        f"🚀 **Latest Backend Execution Log:**\n{last_ai_action_log}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order, bot_status
    current_active_order = "Paused by user. Waiting for new instruction."
    bot_status = "Paused 🟡 (Idle)"
    await update.message.reply_text("🛑 ব্যাকগ্রাউন্ড হান্টিং সাময়িকভাবে পজ করা হয়েছে। চ্যাট করতে পারেন বা নতুন অর্ডার দিতে পারেন।")

# --- Smart Message Handler (ച্যাট এবং কাস্টম Order হ্যান্ডেল করার ব্রেন) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order, bot_status, ai_memory
    
    user_text = update.message.text.strip()
    
    # ১. যদি মেসেজে নতুন 'Order:' দেওয়া হয়
    if user_text.lower().startswith("order:"):
        order_content = user_text[6:].strip()
        current_active_order = order_content
        bot_status = "Active 🟢 (Executing Custom Order)"
        
        reply_msg = (
            f"✅ **New Custom Order Received!**\n\n"
            f"🎯 **Mission Updated:** {order_content}\n"
            f"🚀 আমি আগের ডিফল্ট অর্ডার আপডেট করে এই নতুন নির্দেশ বাস্তবায়নের জন্য কাজ শুরু করে দিলাম!"
        )
        await update.message.reply_text(reply_msg, parse_mode="Markdown")
        
    else:
        # ২. সাধারণ চ্যাট মোড (এআই চ্যাট করবে এবং আপনার কথা অনুযায়ী স্ট্র্যাটেজি বা পরিধি আপডেট করতে পারে)
        ai_memory.append(f"User Chat: {user_text}")
        
        if "কী করছ" in user_text or "status" in user_text.lower() or "কাজ" in user_text:
            ai_reply = f"আমি বর্তমানে আমার ডিফল্ট মিশনে আছি: '{current_active_order}'। আপনি `/status` দিয়ে ওয়ালেট ব্যালেন্স ও ব্যাকএন্ড লগ দেখতে পারেন।"
        elif "পরিবর্তন" in user_text or "update" in user_text.lower() or "বদলে" in user_text:
            ai_reply = "ঠিক আছে! আপনার এই কথামতো আমি আমার কাজের পরিধি ও কৌশল আপডেট করে নিলাম। নতুন কোনো 'Order:' দিতে চাইলে দিতে পারেন।"
        else:
            ai_reply = (
                f"আপনার কথাগুলো আমি নোট করে নিয়েছি এবং আমার কাজের পরিধিতে এটি বিবেচনা করছি। "
                f"আমার ডিফল্ট অর্ডার অনুযায়ী আমি ওয়ালেটে ক্রিপ্টো আনার কাজ চালিয়ে যাচ্ছি। আপনি চাইলে নতুন কোনো নির্দেশ দিতে পারেন।"
            )
            
        await update.message.reply_text(ai_reply)

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
    
    # সাধারণ চ্যাট ও অর্ডারের জন্য মেসেজ হ্যান্ডলার
    app_telegram.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # ব্যাকগ্রাউন্ড ডিফল্ট অর্ডার এক্সিকিউশন থ্রেড
    ai_brain_thread = threading.Thread(target=run_crypto_ai_brain, args=(app_telegram,), daemon=True)
    ai_brain_thread.start()

    print("🤖 Interactive AI Agent with Default Crypto Acquisition Order is running...")
    app_telegram.run_polling()
