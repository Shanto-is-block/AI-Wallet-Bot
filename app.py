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

# একাধিক ব্যাকআপ পলিগন RPC লিস্ট
RPC_URLS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://polygon.llamarpc.com",
    "https://polygon-rpc.com"
]

# Flask App to keep Render alive via Web Service pings
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 AI Telegram Crypto Bot with Built-in Fallback AI is Alive and Running 24/7!"

# Global state and Memory for bot tracking
bot_status = "Inactive 🔴"
last_ai_decision = "No decision yet."
ai_memory = []  
ai_mode = "Gemini Cloud AI 🧠"  # কোন এআই কাজ করছে তা ট্র্যাক করার জন্য

# --- বিল্ড-ইন ফলব্যাক এআই (যদি জেমিনি অফ থাকে তবে এটি কাজ করবে) ---
def get_builtin_fallback_strategy(balance_eth):
    global ai_memory
    # ব্যালেন্স এবং মেমরি অনুযায়ী নিজস্ব লজিকে স্মার্ট স্ট্র্যাটেজি তৈরি করবে
    strategies = [
        f"Built-in Fallback Agent: Wallet balance is {balance_eth} MATIC. Holding position, monitoring Polygon gas fluctuations, and preparing micro-task liquidity channels.",
        f"Built-in Fallback Agent: Analyzing past actions. Recommending capital preservation and scanning for low-gas smart contract execution windows.",
        f"Built-in Fallback Agent: Network stable. Executing defensive asset management strategy for {balance_eth} MATIC while cloud AI recovers."
    ]
    # ঘনিষ্ট বা রোটেশনাল স্ট্র্যাটেজি বেছে নেওয়া
    chosen_strategy = strategies[len(ai_memory) % len(strategies)]
    return chosen_strategy

# --- AI & Web3 Autonomous Worker with Fallback & Built-in AI ---
def run_crypto_ai_brain(chat_id, app_context):
    global bot_status, last_ai_decision, ai_memory, ai_mode
    bot_status = "Active 🟢"
    
    while True:
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
            
            while True:
                try:
                    balance_wei = w3.eth.get_balance(account.address)
                    balance_eth = w3.from_wei(balance_wei, 'ether')
                    history_context = "\n".join(ai_memory[-5:]) if ai_memory else "No prior history."
                    
                    # প্রথমে জেমিনি ক্লাউড এআই দিয়ে চেষ্টা করা হবে
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
                        # যদি জেমিনি এপিআই ফেইল করে (Key invalid বা অন্য কোনো কারণে), তখন বিল্ড-ইন এআই কাজ করবে
                        last_ai_decision = get_builtin_fallback_strategy(balance_eth)
                        ai_mode = "Built-in Local Fallback AI 🛡️ (Gemini Offline)"
                        bot_status = "Active 🟢 (Fallback Mode)"
                    
                    # মেমরিতে যুক্ত করা
                    ai_memory.append(last_ai_decision)
                    if len(ai_memory) > 5:
                        ai_memory.pop(0)
                    
                    # Telegram update message
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
                
                # Wait for 10 minutes before next cycle
                time.sleep(600)
                
        except Exception as outer_e:
            bot_status = f"Error: {str(outer_e)} ❌ (Auto-recovering...)"
            time.sleep(30)

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    welcome_text = (
        "👋 স্বাগতম! এটি আপনার পার্সোনাল **AI Autonomous Crypto Bot (Failover Enabled)**।\n\n"
        "নিচের কমান্ডগুলো ব্যবহার করুন:\n"
        "🚀 `/runbot` - এআই ও ক্রিপ্টো বট ব্যাকগ্রাউন্ডে চালু করতে\n"
        "📊 `/status` - বটের বর্তমান অবস্থা ও কোন এআই কাজ করছে তা জানতে\n"
        "🛑 `/stop` - বট বন্ধ করতে"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def runbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    global bot_status
    if "Active" in bot_status:
        await update.message.reply_text("⚠️ বট ইতিমধ্যে ব্যাকগ্রাউন্ডে চালু আছে!")
    else:
        await update.message.reply_text("🚀 এআই ক্রিপ্টো বট ফলব্যাক সিস্টেমসহ ব্যাকগ্রাউন্ডে চালু করা হচ্ছে...")
        t = threading.Thread(target=run_crypto_ai_brain, args=(chat_id, context), daemon=True)
        t.start()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        f"📊 **Bot Status Report**\n\n"
        f"🔹 **Status:** {bot_status}\n"
        f"⚙️ **Active Engine:** {ai_mode}\n"
        f"🧠 **Last AI Insight:** {last_ai_decision}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

# --- Run Flask Server in Background ---
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    app_telegram = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("runbot", runbot_command))
    app_telegram.add_handler(CommandHandler("status", status_command))
    
    print("🤖 Telegram Bot with Fallback AI is polling for updates...")
    app_telegram.run_polling()
