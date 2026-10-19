import os
import time
import threading
import requests
import json
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import VersionedTransaction
from solders.message import Message
import base58

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8974206752:AAFqOusGoMFjh0snVhUQZFEvt58jJ56FVIk"      
SOLANA_PRIVATE_KEY_BASE58 = "4YEgMCUoSSSR7TE7LGfV4PW3757JRmzvBVbGP4uNFGwCq5ddzfkmiBDPcGL5LqNmLj8CwyTsptzjwXUuSxVYwyBX"      
RENDER_APP_URL = "https://ai-wallet-bot-yy4i.onrender.com" 

# 👉 Groq API Key (সঠিক ছোট হাতের 'gsk_' ফরম্যাটে আপডেট করা হয়েছে)
GROQ_API_KEYS = [
    "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"
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
    return "🤖 Autonomous Crypto AI Trading Agent (Groq & Jupiter DEX Enabled) is Active!"

# Global State
bot_status = "Active 🟢 (Groq Llama AI & Jupiter DEX Trading Engine Running)"
current_active_order = "অটোনমাস মিশন: ট্রেন্ডিং মার্কেট স্ক্যান, Groq AI ডিসিশন এবং জুপিটার ডিইএক্স (Jupiter DEX) এর মাধ্যমে অটো-সোয়াপ ও প্রফিট হান্টিং।"
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
                mint_address = top.get('baseToken', {}).get('address', '')
                return f"Top Trending: {name} ({symbol}) | Mint: `{mint_address}` | Price: ${price} | 6h Change: {change}%"
        return "Market data unavailable."
    except Exception as e:
        return f"Market fetch error: {str(e)[:25]}"

# --- TOOL 3: Automated Token Swap via Jupiter DEX ---
def execute_jupiter_swap(output_mint, amount_sol):
    if amount_sol > 0.02:
        return "❌ [Safety Guardrail Blocked]: সুরক্ষার স্বার্থে একবারে ০.০২ SOL এর বেশি অটো-ট্রেড নিষিদ্ধ।"
    
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "❌ Keypair error."
            
        input_mint = "So11111111111111111111111111111111111111112" # Wrapped SOL
        lamports = int(amount_sol * 1000000000)
        
        quote_url = f"https://quote-jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={lamports}&slippageBps=150"
        quote_res = requests.get(quote_url, timeout=8)
        if quote_res.status_code != 200:
            return f"❌ Jupiter Quote Error: {quote_res.text[:100]}"
        
        quote_data = quote_res.json()
        
        swap_url = "https://quote-jup.ag/v6/swap"
        payload = {
            "quoteResponse": quote_data,
            "userPublicKey": str(keypair.pubkey()),
            "wrapAndUnwrapSol": True
        }
        swap_res = requests.post(swap_url, json=payload, timeout=8)
        if swap_res.status_code != 200:
            return f"❌ Jupiter Swap API Error: {swap_res.text[:100]}"
            
        swap_data = swap_res.json()
        swap_transaction_base64 = swap_data.get("swapTransaction")
        
        raw_tx_bytes = base58.b58decode(swap_transaction_base64)
        tx = VersionedTransaction.from_bytes(raw_tx_bytes)
        
        signature = keypair.sign_message(bytes(tx.message))
        signed_tx = VersionedTransaction.populate(tx.message, [signature])
        
        encoded_tx = base58.b58encode(bytes(signed_tx)).decode('utf-8')
        
        broadcast_payload = {
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "sendTransaction", 
            "params": [encoded_tx, {"encoding": "base58", "maxRetries": 3}]
        }
        
        res = requests.post(SOLANA_RPC_URLS[0], json=broadcast_payload, timeout=10).json()
        
        if "result" in res:
            return f"✅ [Auto-Trade Success] Swap Executed! Tx Signature: `{res['result']}`"
        else:
            return f"❌ RPC Broadcast Error: {res.get('error', 'Unknown')}"
            
    except Exception as e:
        return f"❌ Swap Execution Exception: {str(e)}"

# --- Smart Fallback Brain ---
def rule_based_fallback_brain(balance_sol, market_info):
    advice = "💡 ওয়ালেটে পর্যাপ্ত ফান্ড রয়েছে বা মার্কেট স্ক্যান চলছে।" if balance_sol > 0 else "💡 ওয়ালেটে ০ SOL রয়েছে। গ্যাস ফি যুক্ত করুন।"
    return (
        f"🧠 **[Smart Built-in AI Brain Active]:**\n"
        f"📊 **Market Report:** {market_info}\n"
        f"👛 **Wallet Balance:** {balance_sol} SOL\n"
        f"💡 **Strategic Advice:** {advice}\n"
        f"*(নোট: এপিআই সাময়িকভাবে ব্যস্ত থাকায় ফলব্যাক ইঞ্জিন এই ডিসিশন নিয়েছে)*"
    )

# --- Groq AI Brain Integration ---
def ask_groq_ai_agent(wallet_address, balance_sol, market_info, user_order):
    global current_key_index
    
    valid_keys = [k for k in GROQ_API_KEYS if k and "YOUR_" not in k]
    if not valid_keys:
        return rule_based_fallback_brain(balance_sol, market_info)

    prompt = f"""
    You are an autonomous crypto AI trading agent managing a Solana wallet.
    Current Mission: {user_order}
    Wallet Address: {wallet_address}
    Wallet Balance: {balance_sol} SOL
    Market Info: {market_info}
    
    Analyze the market trends and decide whether conditions are optimal to trigger a buy/swap or hold. Provide strategic insights and answers clearly in Bengali.
    """

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    total_keys = len(valid_keys)
    for _ in range(total_keys):
        active_key = valid_keys[current_key_index % total_keys]
        
        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code in [429, 403, 401]:
                current_key_index = (current_key_index + 1) % total_keys
                continue
                
            if response.status_code == 200:
                res_json = response.json()
                choices = res_json.get('choices', [])
                if choices:
                    text_output = choices[0]['message']['content']
                    return f"🧠 **[Groq Llama AI Trading Brain]:**\n{text_output}"
            
            current_key_index = (current_key_index + 1) % total_keys
        except Exception:
            current_key_index = (current_key_index + 1) % total_keys
            continue

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
            
            ai_thought_process = ask_groq_ai_agent(wallet_address, balance_sol, market_info, current_active_order)

            action_log = (
                f"🎯 **Mission:** {current_active_order}\n"
                f"👛 **Wallet:** `{wallet_address}`\n"
                f"💰 **Balance:** {balance_sol:.4f} SOL\n\n"
                f"{ai_thought_process}"
            )
            last_ai_action_log = action_log
            bot_status = "Active 🟢 (Groq AI & Auto-DEX Trading Engine Healthy)"
            
            ai_memory.append(action_log)
            if len(ai_memory) > 5:
                ai_memory.pop(0)
            
            time.sleep(180) 
                
        except Exception as e:
            bot_status = f"Error: {str(e)[:30]} ❌"
            time.sleep(15)

# --- Telegram Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Autonomous Crypto Trading Agent Activated (Powered by Groq AI)!**\n\n"
        "📈 Groq Llama-3.3 এবং জুপিটার ডিইএক্স (Jupiter DEX) সফলভাবে সংযুক্ত রয়েছে।\n\n"
        "কমান্ডসমূহ:\n"
        "📊 `/status` - লাইভ এআই অ্যানালাইসিস ও ব্যালেন্স দেখতে\n"
        "⚡ `Buy <Token_Mint> <Amount>` - নির্দিষ্ট টোকেন কিনতে\n"
        "🛑 `/stop` - বোট পজ করতে",
        parse_mode="Markdown"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet_address, balance_sol = get_wallet_details()
    market_info = fetch_market_trends()
    ai_thought = ask_groq_ai_agent(wallet_address, balance_sol, market_info, current_active_order)
    
    status_msg = (
        f"📊 **AI Autonomous Trading Live Status**\n\n"
        f"🔹 **Status:** {bot_status}\n"
        f"👛 **Wallet:** `{wallet_address}`\n"
        f"💰 **Balance:** {balance_sol:.4f} SOL\n"
        f"🎯 **Mission:** {current_active_order}\n\n"
        f"{ai_thought}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order, bot_status
    current_active_order = "Paused by user."
    bot_status = "Paused 🟡"
    await update.message.reply_text("🛑 অটোনমাস ট্রেডিং ইঞ্জিন সাময়িকভাবে পজ করা হয়েছে।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_active_order
    user_text = update.message.text.strip()
    
    if user_text.lower().startswith("order:"):
        current_active_order = user_text[6:].strip()
        await update.message.reply_text(f"✅ নতুন এআই মিশন সেট করা হয়েছে: {current_active_order}")
        
    elif user_text.lower().startswith("buy "):
        parts = user_text.split()
        if len(parts) >= 3:
            token_mint = parts[1]
            try:
                amount_sol = float(parts[2])
                await update.message.reply_text(f"⏳ ট্রেড এক্সিকিউট করা হচ্ছে... টোকেন: `{token_mint}`, পরিমাণ: `{amount_sol} SOL`")
                result_msg = execute_jupiter_swap(token_mint, amount_sol)
                await update.message.reply_text(result_msg, parse_mode="Markdown")
            except ValueError:
                await update.message.reply_text("❌ ভুল পরিমাণ (Amount)। সঠিক ফরম্যাট: `Buy <Token_Mint> <Amount>`")
        else:
            await update.message.reply_text("❌ ফরম্যাট সঠিক নয়। ব্যবহার করুন: `Buy <Token_Mint_Address> <SOL_Amount>`")
    else:
        wallet_address, balance_sol = get_wallet_details()
        market_info = fetch_market_trends()
        ai_thought = ask_groq_ai_agent(wallet_address, balance_sol, market_info, current_active_order)
        await update.message.reply_text(
            f"🤖 এআই এজেন্ট রেসপন্স:\n\n{ai_thought}\n\nনতুন ট্রেড করতে ঠিক এভাবে লিখে পাঠান:\n**'Buy <Mint> <Amount>'** অথবা মিশন সেট করতে **'Order:'** লিখে পাঠান।"
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

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pass
        else:
            app_telegram.run_polling()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app_telegram.run_polling()
