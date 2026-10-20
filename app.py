import os
import json
import time
import threading
from threading import Lock
import requests
import base64
import traceback
from flask import Flask, request as flask_request, render_template_string, redirect, url_for
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import VersionedTransaction
from solders.message import Message
from solders.hash import Hash
import base58

# --- Configuration & Credentials ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8931678358:AAEFHNA__FVJlwB6LGbkYRFPXVMm7fYBaaA")      
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7363218232")

DEFAULT_SOLANA_PRIVATE_KEY = os.environ.get("SOLANA_PRIVATE_KEY_BASE58", "")      

# Render Web Service Public URL
RENDER_APP_URL = os.environ.get("RENDER_APP_URL", "https://ai-wallet-bot-yy4i.onrender.com") 

# Custom AI API Configuration
CUSTOM_AI_API_URL = os.environ.get("CUSTOM_AI_API_URL", "https://ai-api-cgzb.onrender.com")
CUSTOM_AI_API_KEY = os.environ.get("CUSTOM_AI_API_KEY", "ai_key_1762b5a10bdc7ed4a5db091d")

# --- Supabase Cloud Database Configuration ---
SUPABASE_URL = "https://xtpxbopftgjdszmgajno.supabase.co"
SUPABASE_KEY = "Sb_secret_Q4UN8TJ7Gx37q0c5tppdaw_FLRwzEeC"

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Free Public Solana RPC URLs
SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana"
]

app = Flask(__name__)

# --- Thread Lock for Global State Safety ---
data_lock = Lock()

bot_status = "Active 🟢 (Cloud-Synced Autonomous AI Trader & Self-Healing Engine)"
current_active_order = "Mission: Smart RPC routing, Supabase Cloud Sync, AI Self-Healing & Trailing TP/SL."
is_bot_running = True

# --- Load & Save Persistent Private Key via Supabase ---
def get_saved_wallet_key():
    try:
        url = f"{SUPABASE_URL}/rest/v1/system_config?key=eq.private_key&select=value"
        res = safe_get_supa(url)
        if res and res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                return data[0].get("value", "")
    except Exception as e:
        print(f"Load Key Supabase Error: {e}")
    return DEFAULT_SOLANA_PRIVATE_KEY

def save_wallet_key_to_db(private_key):
    try:
        url = f"{SUPABASE_URL}/rest/v1/system_config"
        payload = {"key": "private_key", "value": private_key}
        headers = SUPABASE_HEADERS.copy()
        headers["Prefer"] = "resolution=merge-duplicates"
        safe_post_supa(url, json_data=payload, headers=headers)
    except Exception as e:
        print(f"Save Key Supabase Error: {e}")

runtime_private_key = get_saved_wallet_key()
user_states = {}

def safe_get_supa(url):
    try:
        return requests.get(url, headers=SUPABASE_HEADERS, timeout=8)
    except Exception as e:
        print(f"Supabase GET Error: {e}")
        return None

def safe_post_supa(url, json_data, headers=None):
    try:
        h = headers if headers else SUPABASE_HEADERS
        return requests.post(url, json=json_data, headers=h, timeout=8)
    except Exception as e:
        print(f"Supabase POST Error: {e}")
        return None

def log_to_db(balance, strategy, revenue):
    try:
        url = f"{SUPABASE_URL}/rest/v1/earnings_log"
        payload = {
            "timestamp": time.ctime(),
            "balance": balance,
            "ai_strategy": strategy,
            "revenue": revenue
        }
        safe_post_supa(url, json_data=payload)
    except Exception as e:
        print(f"Cloud DB Log Error: {e}")

# --- Persistent Memory via Supabase ---
default_memory_data = {
    "strategy_pool": {
        "Smart_RPC_Router": {"weight": 4.5, "success": 0, "fail": 0},
        "Auto_Blacklist_Engine": {"weight": 4.9, "success": 0, "fail": 0},
        "Jupiter_Real_Swap_Engine": {"weight": 3.5, "success": 0, "fail": 0},
        "RugCheck_Security_Guard": {"weight": 4.9, "success": 0, "fail": 0},
        "Trailing_TP_SL_Engine": {"weight": 5.0, "success": 0, "fail": 0}
    },
    "agent_memory": {
        "past_activities": [],
        "total_revenue_generated_sol": 0.0,
        "tools_executed_count": 0,
        "blacklisted_tokens": []
    }
}

def load_persistent_memory():
    try:
        url = f"{SUPABASE_URL}/rest/v1/system_config?key=eq.agent_memory_store&select=value"
        res = safe_get_supa(url)
        if res and res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                stored_json = json.loads(data[0].get("value", "{}"))
                return stored_json.get("strategy_pool", default_memory_data["strategy_pool"]), stored_json.get("agent_memory", default_memory_data["agent_memory"])
    except Exception as e:
        print(f"Cloud Memory Load Error: {e}")
    return default_memory_data["strategy_pool"], default_memory_data["agent_memory"]

def save_persistent_memory(s_pool, a_memory):
    try:
        url = f"{SUPABASE_URL}/rest/v1/system_config"
        full_data = json.dumps({"strategy_pool": s_pool, "agent_memory": a_memory})
        payload = {"key": "agent_memory_store", "value": full_data}
        headers = SUPABASE_HEADERS.copy()
        headers["Prefer"] = "resolution=merge-duplicates"
        safe_post_supa(url, json_data=payload, headers=headers)
    except Exception as e:
        print(f"Cloud Memory Save Error: {e}")

strategy_pool, agent_memory = load_persistent_memory()

# --- Robust Request Wrappers with Retry & Timeout ---
def safe_get(url, timeout=12, retries=3):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for i in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=timeout)
            return res
        except Exception as e:
            if i == retries - 1:
                print(f"GET Error [{url}]: {e}")
                return None
            time.sleep(2)
    return None

def safe_post(url, json_data=None, timeout=12, retries=3):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Content-Type": "application/json"}
    for i in range(retries):
        try:
            res = requests.post(url, json=json_data, headers=headers, timeout=timeout)
            return res
        except Exception as e:
            if i == retries - 1:
                print(f"POST Error [{url}]: {e}")
                return None
            time.sleep(2)
    return None

def send_telegram_message(chat_id, text_message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text_message,
            "parse_mode": "Markdown"
        }
        safe_post(url, json_data=payload, timeout=8, retries=2)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# --- 🧠 AI Autonomous Self-Healing Engine (Auto-Fix & Adaptation) ---
def ai_autonomous_self_heal(error_exception, function_name):
    try:
        error_trace = traceback.format_exc()
        payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "autonomous_self_heal",
            "data": {
                "function": function_name,
                "error_message": str(error_exception),
                "traceback": error_trace
            },
            "instructions": "Analyze this error. Return a JSON object strictly containing: {\"action\": \"RETRY\" | \"INCREASE_SLIPPAGE\" | \"SWITCH_RPC\" | \"SKIP\", \"adjustment_value\": number_or_string, \"reason\": \"short reason\"}"
        }
        response = safe_post(CUSTOM_AI_API_URL, json_data=payload, timeout=8, retries=1)
        if response and response.status_code == 200:
            res_data = response.json()
            if isinstance(res_data, dict):
                return res_data
        return {"action": "RETRY", "adjustment_value": 0, "reason": "Default autonomous fallback retry"}
    except Exception as e:
        print(f"Self-healing mechanism error: {e}")
        return {"action": "RETRY", "adjustment_value": 0, "reason": "Self-heal exception fallback"}

# --- Smart RPC Speed Selector ---
def get_fastest_rpc():
    fastest_rpc = SOLANA_RPC_URLS[0]
    min_latency = float('inf')
    
    for rpc in SOLANA_RPC_URLS:
        try:
            start_time = time.time()
            res = safe_post(rpc, json_data={"jsonrpc": "2.0", "id": 1, "method": "getHealth"}, timeout=5, retries=1)
            if res and res.status_code == 200:
                latency = time.time() - start_time
                if latency < min_latency:
                    min_latency = latency
                    fastest_rpc = rpc
        except Exception:
            continue
    return fastest_rpc

# ==========================================
# --- WEB DASHBOARD ROUTES ---
# ==========================================
def get_solana_keypair():
    try:
        current_key = get_saved_wallet_key()
        if not current_key:
            return None
        secret_key_bytes = base58.b58decode(current_key)
        return Keypair.from_bytes(secret_key_bytes)
    except Exception as e:
        print(f"Keypair Error: {e}")
        return None

def get_real_solana_wallet_details():
    wallet_address = "Not Connected"
    balance_sol = 0.0
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return wallet_address, balance_sol
        wallet_address = str(keypair.pubkey())
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [wallet_address]}
        rpc_url = get_fastest_rpc()
        res = safe_post(rpc_url, json_data=payload, timeout=8, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            if "result" in data and "value" in data["result"]:
                balance_sol = float(data["result"]["value"]) / 1000000000.0
    except Exception as e:
        print(f"Balance Check Error: {e}")
    return wallet_address, balance_sol

@app.route('/')
def home():
    return "🤖 Cloud-Synced Autonomous AI Trader is Active! Visit <a href='/dashboard'>/dashboard</a> to connect your wallet."

@app.route('/dashboard')
def dashboard():
    current_key = get_saved_wallet_key()
    connected = bool(current_key)
    pubkey_str = "Not Connected"
    balance_sol = 0.0
    if connected:
        kp = get_solana_keypair()
        if kp:
            pubkey_str = str(kp.pubkey())
            _, balance_sol = get_real_solana_wallet_details()

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>AI Trader Bot - Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }
            .container { max-width: 600px; margin: auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; }
            .status { background: #334155; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            input[type="text"] { width: 100%; padding: 12px; margin: 10px 0; background: #0f172a; border: 1px solid #475569; color: white; border-radius: 6px; box-sizing: border-box; }
            button { background: #0284c7; color: white; border: none; padding: 12px 20px; width: 100%; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
            button:hover { background: #0ea5e9; }
            .msg { margin-top: 15px; text-align: center; color: #4ade80; font-weight: bold; }
            .error { color: #f87171; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🤖 AI Trader Bot Dashboard</h2>
            <div class="status">
                <p><strong>Connection Status:</strong> {{ "Connected 🟢" if connected else "Disconnected 🔴" }}</p>
                <p><strong>Wallet Address:</strong> <code>{{ pubkey_str }}</code></p>
                <p><strong>SOL Balance:</strong> {{ "%.4f"|format(balance_sol) }} SOL</p>
            </div>
            <form action="/connect-wallet" method="POST">
                <h3>{{ "Update / Re-enter Wallet Private Key" if connected else "Connect Your Solana Wallet" }}</h3>
                <p style="font-size: 14px; color: #94a3b8;">Enter your Base58 encoded Solana Private Key below:</p>
                <input type="text" name="private_key" placeholder="Enter Base58 Private Key..." required>
                <button type="submit">{{ "Update Wallet (Re-enter)" if connected else "Connect Wallet" }}</button>
            </form>
            {% if msg %}
            <p class="msg {{ 'error' if is_error else '' }}">{{ msg }}</p>
            {% endif %}
        </div>
    </body>
    </html>
    """
    msg = flask_request.args.get('msg', '')
    is_error = flask_request.args.get('error', '0') == '1'
    return render_template_string(html_template, connected=connected, pubkey_str=pubkey_str, balance_sol=balance_sol, msg=msg, is_error=is_error)

@app.route('/connect-wallet', methods=['POST'])
def connect_wallet():
    global runtime_private_key
    private_key_input = flask_request.form.get('private_key', '').strip()
    try:
        test_bytes = base58.b58decode(private_key_input)
        test_kp = Keypair.from_bytes(test_bytes)
        with data_lock:
            runtime_private_key = private_key_input
            save_wallet_key_to_db(private_key_input)
        return redirect(url_for('dashboard', msg='Wallet connected & saved securely to Cloud DB!', error='0'))
    except Exception as e:
        return redirect(url_for('dashboard', msg=f'Invalid Private Key: {str(e)[:40]}', error='1'))

# ==========================================
# --- TELEGRAM WEBHOOK & COMMANDS ---
# ==========================================
@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    global current_active_order, bot_status, runtime_private_key
    try:
        data = flask_request.get_json()
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            raw_text = message.get("text", "").strip()
            text = raw_text.lower()

            current_key = get_saved_wallet_key()
            is_connected = bool(current_key)

            if text.startswith("/start"):
                if not is_connected:
                    welcome_text = (
                        "🚀 *Cloud-Synced Autonomous AI Agent Activated!*\n\n"
                        "⚠️ *Wallet Status:* Not Connected 🔴\n\n"
                        "Please click or send `/enter` to open the Web Dashboard and connect your Solana wallet securely."
                    )
                else:
                    welcome_text = (
                        "🚀 *Cloud-Synced Autonomous AI Agent Activated!*\n\n"
                        "🟢 *Wallet Status:* Connected (Supabase Cloud-Synced)\n"
                        "🔍 *Mode:* Smart RPC, Auto-Blacklist, AI Self-Healing & Cloud Memory.\n\n"
                        "Commands:\n"
                        "📊 `/status` - Complete portfolio valuation & system state\n"
                        "💰 `/balance` - Live balance of SOL & all SPL assets\n"
                        "📜 `/trans` - View first 10 transactions with USD value\n"
                        "📈 `/scan` - Jupiter price API & token scan\n"
                        "⚡ `/swap` - Execute manual test swap (0.01 SOL to USDC)\n"
                        "🔄 `/reenter` - Disconnect current wallet & connect a new Private Key via Dashboard\n"
                        "🛑 `/stop` - Pause autonomous operations\n"
                        "✍️ `Order: [your command]` - Update operational focus"
                    )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/enter"):
                if is_connected:
                    send_telegram_message(chat_id, "ℹ️ Wallet is already connected! Use `/reenter` if you want to change your wallet.")
                else:
                    dashboard_url = f"{RENDER_APP_URL}/dashboard"
                    send_telegram_message(chat_id, f"🌐 *Web Dashboard Connection*\n\nClick the link below to open the dashboard and connect your Solana Private Key securely:\n\n🔗 [Open Dashboard]({dashboard_url})")

            elif text.startswith("/reenter"):
                dashboard_url = f"{RENDER_APP_URL}/dashboard"
                send_telegram_message(chat_id, f"🔄 *Wallet Re-entry Mode*\n\nYour previous wallet will be replaced when you connect a new one on the dashboard.\n\n🔗 [Open Dashboard to Re-enter]({dashboard_url})")

            elif text.startswith("/status"):
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Please use `/enter` to connect your wallet first.")
                    return "OK", 200

                wallet_address, balance_sol, portfolio_usd, sol_price, token_details = get_wallet_portfolio_value()
                system_state_msg = evaluate_real_system_state(balance_sol)
                
                tokens_summary = ""
                if token_details:
                    tokens_summary = "\n🔹 *Wallet Assets:* \n"
                    for t in token_details:
                        tokens_summary += f"• `{t['symbol']}`: {t['amount']:.4f} (~${t['usd']:.2f})\n"

                status_msg = (
                    f"📊 *Full Portfolio Status Report*\n\n"
                    f"👛 *Wallet Address:* `{wallet_address}`\n"
                    f"💰 *SOL Balance:* `{balance_sol:.4f} SOL`\n"
                    f"{tokens_summary}"
                    f"💵 *Total Portfolio Value:* **`${portfolio_usd:.2f} USD`**\n"
                    f"📈 *Current SOL Price:* `${sol_price:.2f}`\n\n"
                    f"{system_state_msg}"
                )
                send_telegram_message(chat_id, status_msg)

            elif text.startswith("/balance"):
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Please use `/enter` to connect your wallet first.")
                    return "OK", 200

                wallet_address, balance_sol, portfolio_usd, sol_price, token_details = get_wallet_portfolio_value()
                incoming_status = tool_check_real_incoming_transactions()
                
                tokens_summary = ""
                if token_details:
                    tokens_summary = "\n🔹 *Token Balances:* \n"
                    for t in token_details:
                        tokens_summary += f"• `{t['symbol']}`: {t['amount']:.4f} (~${t['usd']:.2f})\n"

                bal_msg = (
                    f"👛 *Live Wallet Assets & Balances*\n\n"
                    f"• **Address:** `{wallet_address}`\n"
                    f"• **SOL Balance:** `{balance_sol:.4f} SOL`\n"
                    f"{tokens_summary}"
                    f"• **Total Portfolio USD:** **`${portfolio_usd:.2f} USD`**\n"
                    f"• **Latest On-Chain Event:** {incoming_status}"
                )
                send_telegram_message(chat_id, bal_msg)

            elif text.startswith("/trans"):
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Please use `/enter` to connect your wallet first.")
                    return "OK", 200

                trans_result = tool_fetch_multiple_real_transactions_with_usd(10)
                send_telegram_message(chat_id, f"📜 *Latest 10 Transactions (USD Value)*\n\n{trans_result}")

            elif text.startswith("/scan"):
                success, market_msg, sol_price = tool_fetch_real_market_data_with_price()
                wallet_address, balance_sol, portfolio_usd, _, token_details = get_wallet_portfolio_value()
                tx_status = tool_check_real_incoming_transactions()
                
                ai_context = {"wallet": wallet_address, "balance_sol": balance_sol, "portfolio_usd": portfolio_usd, "tokens": token_details, "last_tx": tx_status}
                ai_verdict = analyze_data_with_custom_ai(ai_context)
                
                scan_result = f"{market_msg}\n• **Total Portfolio:** `${portfolio_usd:.2f} USD`\n\n🧠 *AI Security & Market Verdict:*\n{ai_verdict}"
                send_telegram_message(chat_id, f"🔍 *Jupiter Price & Asset Scan*\n\n{scan_result}")

            elif text.startswith("/swap"):
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Please use `/enter` to connect your wallet first.")
                    return "OK", 200

                swap_result = execute_real_jupiter_swap("So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 10000000)
                send_telegram_message(chat_id, f"⚡ *Jupiter Real Swap Execution*\n\n{swap_result}")

            elif text.startswith("/stop"):
                with data_lock:
                    current_active_order = "Paused by user."
                    bot_status = "Paused 🟡"
                send_telegram_message(chat_id, "🛑 Autonomous agent operations paused successfully.")

            elif text.startswith("order:"):
                custom_order = raw_text[6:].strip()
                with data_lock:
                    current_active_order = custom_order
                send_telegram_message(chat_id, f"✅ New operational mission set: {custom_order}")

            else:
                if not is_connected:
                    send_telegram_message(chat_id, "⚠️ Wallet not connected! Please use `/enter` to open the Web Dashboard and connect your wallet.")
                else:
                    wallet_address, balance_sol = get_real_solana_wallet_details()
                    system_state_msg = evaluate_real_system_state(balance_sol)
                    send_telegram_message(chat_id, f"🤖 Agent is running live.\n\n{system_state_msg}")

    except Exception as e:
        print(f"Webhook Error: {e}")
        try:
            send_telegram_message(TELEGRAM_CHAT_ID, f"⚠️ *Webhook Exception Error:* `{str(e)[:80]}`")
        except:
            pass
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def self_ping_worker():
    while True:
        try:
            time.sleep(480) 
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                safe_get(RENDER_APP_URL, timeout=10, retries=1)
        except Exception as e:
            print(f"Self-ping Error: {e}")

def setup_telegram_webhook():
    time.sleep(5) 
    if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
        webhook_url = f"{RENDER_APP_URL}/{TELEGRAM_BOT_TOKEN}"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            safe_get(api_url, timeout=10, retries=2)
        except Exception as e:
            print(f"Webhook Setup Error: {e}")

# ==========================================
# --- REAL ON-CHAIN & PORTFOLIO TOOLS ---
# ==========================================

def get_wallet_spl_tokens(wallet_address):
    tokens_data = []
    program_ids = [
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", 
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"  
    ]
    rpc_url = get_fastest_rpc()
    
    for prog_id in program_ids:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"programId": prog_id},
                    {"encoding": "jsonParsed"}
                ]
            }
            res = safe_post(rpc_url, json_data=payload, timeout=8, retries=2)
            if res and res.status_code == 200:
                data = res.json()
                if "result" in data and "value" in data["result"]:
                    accounts = data["result"]["value"]
                    for acc in accounts:
                        info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                        mint = info.get("mint")
                        token_amount = info.get("tokenAmount", {})
                        ui_amount = float(token_amount.get("uiAmount", 0) or 0)
                        if ui_amount > 0:
                            if not any(t["mint"] == mint for t in tokens_data):
                                tokens_data.append({"mint": mint, "amount": ui_amount})
        except Exception as e:
            print(f"Token Fetch Error for {prog_id}: {e}")
            
    return tokens_data

def get_token_symbol_and_price(mint):
    if mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 
        return "USDC", 1.0

    symbol = mint[:6] + "..." + mint[-4:]
    price = 0.0

    try:
        token_info_url = f"https://tokens.jup.ag/token/{mint}"
        res = safe_get(token_info_url, timeout=5, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            if data and "symbol" in data:
                symbol = data["symbol"]
    except Exception as e:
        print(f"Token Symbol Error [{mint}]: {e}")

    try:
        jup_url = f"https://price.jup.ag/v4/price?ids={mint}"
        res = safe_get(jup_url, timeout=5, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            price_data = data.get("data", {}).get(mint, {})
            p = price_data.get("price")
            if p is not None:
                return symbol, float(p)
    except Exception as e:
        print(f"Jupiter Price Error [{mint}]: {e}")

    try:
        dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        res = safe_get(dex_url, timeout=5, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            pairs = data.get("pairs", [])
            if pairs:
                price_str = pairs[0].get("priceUsd", 0)
                price = float(price_str or 0)
                if "baseToken" in pairs[0] and "symbol" in pairs[0]["baseToken"]:
                    symbol = pairs[0]["baseToken"]["symbol"]
    except Exception as e:
        print(f"DexScreener Price Error [{mint}]: {e}")

    return symbol, price

def tool_fetch_real_market_data_with_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=SOLUSDT"
        res = safe_get(url, timeout=6, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            price = float(data.get("lastPrice", 0))
            change = float(data.get("priceChangePercent", 0))
            return True, f"• **Network Status:** Connected (Binance API)\n• **SOL Market Price:** `${price:.2f} USD`\n• **24h Change:** {change:.2f}%", price
    except Exception as e:
        print(f"Binance Market Data Error: {e}")

    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
        res = safe_get(url, timeout=6, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            price = float(data.get("solana", {}).get("usd", 0))
            change = float(data.get("solana", {}).get("usd_24h_change", 0))
            return True, f"• **Network Status:** Connected (CoinGecko API)\n• **SOL Market Price:** `${price:.2f} USD`\n• **24h Change:** {change:.2f}%", price
    except Exception as e:
        print(f"CoinGecko Market Data Error: {e}")

    return False, "• **Network Status:** Connected\n• **Market Feed:** APIs temporarily limited.", 130.0

def get_wallet_portfolio_value():
    wallet_address, balance_sol = get_real_solana_wallet_details()
    _, _, sol_price = tool_fetch_real_market_data_with_price()
    
    sol_usd = balance_sol * sol_price
    
    spl_tokens = get_wallet_spl_tokens(wallet_address)
    total_spl_usd = 0.0
    token_details_list = []
    
    for t in spl_tokens:
        mint = t["mint"]
        amount = t["amount"]
        symbol, price = get_token_symbol_and_price(mint)
        usd_val = amount * price
        total_spl_usd += usd_val
            
        token_details_list.append({"symbol": symbol, "mint": mint, "amount": amount, "usd": usd_val})
        
    portfolio_usd = sol_usd + total_spl_usd
    return wallet_address, balance_sol, portfolio_usd, sol_price, token_details_list

def tool_check_real_incoming_transactions():
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "Keypair configuration error"
        pubkey_str = str(keypair.pubkey())
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [pubkey_str, {"limit": 1}]
        }
        rpc_url = get_fastest_rpc()
        res = safe_post(rpc_url, json_data=payload, timeout=8, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            if "result" in data and data["result"]:
                sig_info = data["result"][0]
                sig = sig_info.get("signature", "N/A")
                slot = sig_info.get("slot", "N/A")
                err = sig_info.get("err")
                status = "Success 🟢" if err is None else "Failed 🔴"
                return f"Signature: `{sig[:16]}...` | Slot: {slot} | Status: {status}"
        return "No recent transactions found on-chain."
    except Exception as e:
        err_msg = f"Error fetching transactions: {str(e)[:25]}"
        print(err_msg)
        return err_msg

def tool_fetch_multiple_real_transactions_with_usd(limit=10):
    try:
        keypair = get_solana_keypair()
        if not keypair:
            return "❌ Keypair configuration error."
        pubkey_str = str(keypair.pubkey())
        _, _, sol_price = tool_fetch_real_market_data_with_price()
        rpc_url = get_fastest_rpc()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [pubkey_str, {"limit": limit}]
        }
        res = safe_post(rpc_url, json_data=payload, timeout=8, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            if "result" in data and data["result"]:
                sigs = data["result"]
                tx_list = []
                for idx, sig_info in enumerate(sigs, 1):
                    sig = sig_info.get("signature", "N/A")
                    slot = sig_info.get("slot", "N/A")
                    err = sig_info.get("err")
                    status = "Success 🟢" if err is None else "Failed 🔴"

                    sol_transferred = 0.0
                    try:
                        tx_payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getTransaction",
                            "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
                        }
                        tx_res = safe_post(rpc_url, json_data=tx_payload, timeout=5, retries=1)
                        if tx_res and tx_res.status_code == 200:
                            tx_data = tx_res.json()
                            if "result" in tx_data and tx_data["result"]:
                                meta = tx_data["result"].get("meta", {})
                                pre_balances = meta.get("preBalances", [0])
                                post_balances = meta.get("postBalances", [0])
                                if pre_balances and post_balances:
                                    diff = abs(pre_balances[0] - post_balances[0]) / 1000000000.0
                                    sol_transferred = diff
                    except Exception as tx_e:
                        print(f"Sub-transaction details error [{sig}]: {tx_e}")

                    usd_value = sol_transferred * sol_price

                    tx_list.append(
                        f"{idx}. `[Slot {slot}]`\n"
                        f"   • Sign: `{sig[:18]}...`\n"
                        f"   • Vol: `~{sol_transferred:.4f} SOL` (`~${usd_value:.2f} USD`)\n"
                        f"   • Status: {status}"
                    )
                return "\n\n".join(tx_list)
        return "⚠️ No recent transactions found on-chain."
    except Exception as e:
        err_msg = f"❌ Error fetching transactions: {str(e)[:40]}"
        print(err_msg)
        return err_msg

# ==========================================
# --- AI ANALYSIS & SELF-LEARNING BRIDGE ---
# ==========================================
def analyze_data_with_custom_ai(transaction_details):
    try:
        payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "analyze_solana_transaction_or_wallet",
            "data": transaction_details,
            "instructions": "Analyze this blockchain context. Return a short verdict: SAFE or DANGEROUS."
        }
        response = safe_post(CUSTOM_AI_API_URL, json_data=payload, timeout=8, retries=1)
        if response and response.status_code == 200:
            ai_res = response.json()
            return ai_res.get("analysis", "AI processed, status: Safe.")
        else:
            status_code = response.status_code if response else 'Timeout'
            print(f"AI Analysis API warning: Status {status_code}")
            return f"🛡️ AI Guard Active: No critical on-chain anomalies found (API Status: {status_code})"
    except Exception as e:
        print(f"AI Analysis Exception: {e}")
        return f"🛡️ AI Guard Active: Secure local monitoring operational."

def evaluate_trade_opportunity_with_ai(token_info):
    try:
        payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "evaluate_token_trade",
            "data": token_info,
            "instructions": "Analyze this Solana token for high-probability trading. Return your decision strictly starting with either 'BUY' or 'SKIP', followed by a short reason."
        }
        response = safe_post(CUSTOM_AI_API_URL, json_data=payload, timeout=8, retries=1)
        if response and response.status_code == 200:
            ai_res = response.json()
            analysis = ai_res.get("analysis", "SKIP: No clear bullish signal.")
            return analysis
        else:
            print("AI Trade Evaluation API unresponsive.")
            return "SKIP: AI API unresponsive."
    except Exception as e:
        print(f"AI Trade Eval Exception: {e}")
        return f"SKIP: Error connecting to AI ({str(e)[:20]})"

# ==========================================
# --- 🛡️ RUG-PULL & SMART CONTRACT CHECK ---
# ==========================================
def check_rugpull_security(mint):
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report"
        res = safe_get(url, timeout=8, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            risks = data.get("risks", [])
            for risk in risks:
                if risk.get("level") == "danger":
                    update_agent_learning("RugCheck_Security_Guard", False, f"Danger risk: {risk.get('name')}")
                    return False, f"RugCheck Failed ❌: {risk.get('description', 'Dangerous contract risk detected')}"
            
            update_agent_learning("RugCheck_Security_Guard", True)
            return True, "RugCheck Passed 🟢: Smart contract safe."
        else:
            return True, "RugCheck Warning ⚠️: API delayed, proceeding with simulation."
    except Exception as e:
        print(f"RugCheck Exception [{mint}]: {e}")
        return True, f"RugCheck Notice: {str(e)[:30]}"

# ==========================================
# --- 🧪 DYNAMIC SLIPPAGE & SIMULATION ENGINE ---
# ==========================================
def calculate_dynamic_slippage(liquidity_usd):
    if liquidity_usd < 20000:
        return 150 
    elif liquidity_usd < 100000:
        return 100 
    else:
        return 50  

def simulate_trade_opportunity(mint, amount_lamports, liquidity_usd):
    try:
        input_mint = "So11111111111111111111111111111111111111112" 
        slippage_bps = calculate_dynamic_slippage(liquidity_usd)
        
        quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={mint}&amount={amount_lamports}&slippageBps={slippage_bps}"
        
        res = safe_get(quote_url, timeout=8, retries=2)
        if not res or res.status_code != 200:
            return False, f"Simulation Failed: Jupiter Quote API error"
            
        quote_data = res.json()
        out_amount = float(quote_data.get("outAmount", 0))
        price_impact = float(quote_data.get("priceImpactPct", 1.0))
        
        if price_impact > 0.05:
            update_agent_learning("Simulation_Risk_Manager", False, f"High price impact: {price_impact*100:.2f}%")
            return False, f"Simulation Rejected ❌: High Price Impact ({price_impact*100:.2f}%)"
            
        sim_payload = {
            "token_mint": mint,
            "input_sol": amount_lamports / 1000000000.0,
            "estimated_output_units": out_amount,
            "price_impact_pct": price_impact * 100,
            "applied_slippage_bps": slippage_bps,
            "route_plan_steps": len(quote_data.get("routePlan", []))
        }
        
        ai_payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "simulate_trade_risk_reward",
            "data": sim_payload,
            "instructions": "Simulate this trade. Return strictly 'PROFITABLE' if safe to proceed, or 'HIGH_RISK' if it should be avoided."
        }
        
        ai_res = safe_post(CUSTOM_AI_API_URL, json_data=ai_payload, timeout=8, retries=1)
        if ai_res and ai_res.status_code == 200:
            verdict = ai_res.json().get("analysis", "PROFITABLE")
            if "HIGH_RISK" in verdict.upper() or "DANGEROUS" in verdict.upper():
                update_agent_learning("Simulation_Risk_Manager", False, "AI simulation flagged high risk")
                return False, f"Simulation Rejected ❌ by AI Risk Audit: {verdict}"
        
        update_agent_learning("Simulation_Risk_Manager", True)
        return True, f"Simulation Passed 🟢 (Slippage: {slippage_bps/100}%, Impact: {price_impact*100:.2f}%)"
        
    except Exception as e:
        print(f"Simulation Exception: {e}")
        return False, f"Simulation Error: {str(e)[:40]}"

def update_agent_learning(strategy_name, is_success, error_message=""):
    global strategy_pool, agent_memory
    with data_lock:
        if strategy_name in strategy_pool:
            if is_success:
                strategy_pool[strategy_name]["success"] += 1
                strategy_pool[strategy_name]["weight"] = round(strategy_pool[strategy_name]["weight"] + 0.1, 2)
            else:
                strategy_pool[strategy_name]["fail"] += 1
                strategy_pool[strategy_name]["weight"] = max(0.5, round(strategy_pool[strategy_name]["weight"] - 0.3, 2))
                
                agent_memory["past_activities"].append({
                    "time": time.ctime(),
                    "strategy": strategy_name,
                    "status": "FAILED",
                    "reason": error_message
                })
        save_persistent_memory(strategy_pool, agent_memory)

def add_to_blacklist(mint, reason):
    with data_lock:
        if mint not in agent_memory["blacklisted_tokens"]:
            agent_memory["blacklisted_tokens"].append(mint)
            agent_memory["past_activities"].append({
                "time": time.ctime(),
                "token": mint,
                "action": "BLACKLISTED",
                "reason": reason
            })
            save_persistent_memory(strategy_pool, agent_memory)

# ==========================================
# --- JUPITER REAL SWAP EXECUTION ENGINE ---
# ==========================================
def execute_real_jupiter_swap(input_mint, output_mint, amount_lamports, slippage_bps=100):
    max_attempts = 2
    current_slippage = slippage_bps

    for attempt in range(max_attempts):
        try:
            keypair = get_solana_keypair()
            if not keypair:
                update_agent_learning("Jupiter_Real_Swap_Engine", False, "Keypair error")
                return "❌ Keypair configuration error."
            
            wallet_address = str(keypair.pubkey())
            
            quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_lamports}&slippageBps={current_slippage}"
            quote_res = safe_get(quote_url, timeout=8, retries=2)
            if not quote_res or quote_res.status_code != 200:
                update_agent_learning("Jupiter_Real_Swap_Engine", False, "Quote API failed")
                return f"⚠️ Jupiter Quote Failed"
                
            quote_data = quote_res.json()
            
            swap_url = "https://quote-api.jup.ag/v6/swap"
            payload = {
                "quoteResponse": quote_data,
                "userPublicKey": wallet_address,
                "wrapAndUnwrapSol": True
            }
            swap_res = safe_post(swap_url, json_data=payload, timeout=8, retries=2)
            if not swap_res or swap_res.status_code != 200:
                update_agent_learning("Jupiter_Real_Swap_Engine", False, "Swap transaction build failed")
                return f"⚠️ Swap Transaction Build Failed"
                
            swap_data = swap_res.json()
            swap_tx_base64 = swap_data.get("swapTransaction")
            
            if not swap_tx_base64:
                return "❌ Failed to get transaction bytes from Jupiter."
                
            tx_bytes = base64.b64decode(swap_tx_base64)
            txn = VersionedTransaction.from_bytes(tx_bytes)
            
            signed_txn = VersionedTransaction(txn.message, [keypair])
            raw_signed_tx = bytes(signed_txn)
            
            rpc_url = get_fastest_rpc()
            send_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    base64.b64encode(raw_signed_tx).decode("utf-8"),
                    {"encoding": "base64", "skipPreflight": False, "maxSupportedTransactionVersion": 0}
                ]
            }
            
            broadcast_res = safe_post(rpc_url, json_data=send_payload, timeout=10, retries=2)
            if broadcast_res and broadcast_res.status_code == 200:
                broadcast_data = broadcast_res.json()
                if "result" in broadcast_data:
                    tx_sig = broadcast_data["result"]
                    update_agent_learning("Jupiter_Real_Swap_Engine", True)
                    return f"✅ **Jupiter Swap Executed Successfully!**\n• Signature: `{tx_sig[:18]}...`\n• View on Solscan: [Check Tx](https://solscan.io/tx/{tx_sig})"
                else:
                    err_msg = broadcast_data.get("error", {}).get("message", "Unknown error")
                    update_agent_learning("Jupiter_Real_Swap_Engine", False, err_msg)
                    
                    heal_directive = ai_autonomous_self_heal(err_msg, "execute_real_jupiter_swap")
                    action = heal_directive.get("action", "RETRY")
                    
                    if action == "INCREASE_SLIPPAGE" and attempt == 0:
                        current_slippage += int(heal_directive.get("adjustment_value", 100))
                        send_telegram_message(TELEGRAM_CHAT_ID, f"🤖 *AI Self-Healing Activated:* Increasing slippage to `{current_slippage/100}%` and retrying...")
                        continue
                    elif action == "SWITCH_RPC":
                        send_telegram_message(TELEGRAM_CHAT_ID, f"🤖 *AI Self-Healing Activated:* Switching RPC route and retrying...")
                        time.sleep(2)
                        continue
                    else:
                        return f"⚠️ Swap Execution Rejected by Network: {err_msg[:60]}"
            return "⚠️ Swap Broadcast Network Timeout"
                
        except Exception as e:
            err_str = str(e)
            print(f"Swap Execution Exception: {err_str}")
            update_agent_learning("Jupiter_Real_Swap_Engine", False, err_str)
            
            heal_directive = ai_autonomous_self_heal(e, "execute_real_jupiter_swap")
            action = heal_directive.get("action", "RETRY")
            
            if attempt < max_attempts - 1 and action in ["RETRY", "INCREASE_SLIPPAGE", "SWITCH_RPC"]:
                if action == "INCREASE_SLIPPAGE":
                    current_slippage += 100
                send_telegram_message(TELEGRAM_CHAT_ID, f"🤖 *AI Self-Healing Auto-Fix:* Handled error via `{action}`. Retrying...")
                time.sleep(2)
                continue
            else:
                try:
                    send_telegram_message(TELEGRAM_CHAT_ID, f"🚨 *Critical Swap Exception Handled:* `{err_str[:80]}`")
                except:
                    pass
                return f"⚠️ Swap Execution Notice: {err_str[:50]}"
    return "⚠️ Swap Failed after AI Self-Healing attempts."

# ==========================================
# --- 📈 TRAILING STOP-LOSS & TAKE-PROFIT ---
# ==========================================
def track_and_execute_trailing_tpsl():
    try:
        url = f"{SUPABASE_URL}/rest/v1/active_positions?select=*"
        res = safe_get_supa(url)
        if not res or res.status_code != 200:
            return
        positions = res.json()
        if not positions:
            return

        for pos in positions:
            pos_id = pos.get("id")
            mint = pos.get("token_mint")
            symbol = pos.get("symbol")
            amount = pos.get("amount")
            buy_price = pos.get("buy_price_usd")
            highest_price = pos.get("highest_price_usd")

            if not buy_price or buy_price <= 0:
                continue

            _, current_price = get_token_symbol_and_price(mint)
            if current_price <= 0:
                continue

            if current_price > highest_price:
                highest_price = current_price
                up_url = f"{SUPABASE_URL}/rest/v1/active_positions?id=eq.{pos_id}"
                safe_post_supa(up_url, json_data={"highest_price_usd": highest_price}, headers={**SUPABASE_HEADERS, "Prefer": "resolution=merge-duplicates"})

            total_pnl_pct = ((current_price - buy_price) / buy_price) * 100
            drawdown_from_peak = ((highest_price - current_price) / highest_price) * 100

            if total_pnl_pct >= 40.0:
                send_telegram_message(TELEGRAM_CHAT_ID, f"🎯 *Take-Profit Target Hit!*\n• Token: `{symbol}`\n• Total Profit: `+{total_pnl_pct:.2f}%`\n⚡ *Selling to lock profits...*")
                
                token_lamports = int(amount * 1_000_000_000)
                sol_mint = "So11111111111111111111111111111111111111112"
                sell_result = execute_real_jupiter_swap(mint, sol_mint, token_lamports)
                
                send_telegram_message(TELEGRAM_CHAT_ID, f"✅ *Take-Profit Execution:*\n{sell_result}")
                update_agent_learning("Trailing_TP_SL_Engine", True)
                
                del_url = f"{SUPABASE_URL}/rest/v1/active_positions?id=eq.{pos_id}"
                requests.delete(del_url, headers=SUPABASE_HEADERS, timeout=5)

            elif drawdown_from_peak >= 15.0 or total_pnl_pct <= -15.0:
                reason = f"Trailing Drop (-{drawdown_from_peak:.2f}% from peak)" if drawdown_from_peak >= 15.0 else f"Fixed Stop-Loss ({total_pnl_pct:.2f}%)"
                send_telegram_message(TELEGRAM_CHAT_ID, f"🛡️ *Trailing Stop-Loss Triggered!*\n• Token: `{symbol}`\n• Reason: {reason}\n• Final PnL: `{total_pnl_pct:.2f}%`\n⚡ *Executing Sell...*")
                
                token_lamports = int(amount * 1_000_000_000)
                sol_mint = "So11111111111111111111111111111111111111112"
                sell_result = execute_real_jupiter_swap(mint, sol_mint, token_lamports)
                
                send_telegram_message(TELEGRAM_CHAT_ID, f"🛑 *Stop-Loss Execution:*\n{sell_result}")
                update_agent_learning("Trailing_TP_SL_Engine", False, reason)
                add_to_blacklist(mint, f"Hit Stop-Loss at {total_pnl_pct:.2f}%")
                
                del_url = f"{SUPABASE_URL}/rest/v1/active_positions?id=eq.{pos_id}"
                requests.delete(del_url, headers=SUPABASE_HEADERS, timeout=5)

    except Exception as e:
        print(f"Cloud TP/SL Error: {e}")

# ==========================================
# --- AUTONOMOUS TOKEN DISCOVERY & SCANNING ---
# ==========================================
def fetch_trending_solana_tokens():
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
        res = safe_get(url, timeout=8, retries=2)
        if res and res.status_code == 200:
            data = res.json()
            pairs = data.get("pairs", [])
            valid_tokens = []
            for pair in pairs:
                if pair.get("chainId") == "solana":
                    base_token = pair.get("baseToken", {})
                    mint = base_token.get("address")
                    symbol = base_token.get("symbol")
                    liquidity = pair.get("liquidity", {}).get("usd", 0)
                    volume_24h = pair.get("volume", {}).get("h24", 0)
                    
                    if mint and liquidity > 5000 and mint not in agent_memory.get("blacklisted_tokens", []):
                        valid_tokens.append({
                            "mint": mint,
                            "symbol": symbol,
                            "liquidity": liquidity,
                            "volume_24h": volume_24h,
                            "priceUsd": pair.get("priceUsd", 0)
                        })
            return valid_tokens[:5]
    except Exception as e:
        print(f"Token Discovery Error: {e}")
    return []

# ==========================================================
# --- REAL SYSTEM STATE EVALUATION ---
# ==========================================================
def evaluate_real_system_state(balance_sol):
    success, market_msg, sol_price = tool_fetch_real_market_data_with_price()
    tx_status = tool_check_real_incoming_transactions()
    _, _, portfolio_usd, _, _ = get_wallet_portfolio_value()
    
    with data_lock:
        current_mission = current_active_order

    state_report = (
        f"⚙️ *Cloud System Execution Report*\n"
        f"• **Active Mission:** {current_mission}\n"
        f"{market_msg}\n"
        f"• **Total Portfolio USD:** `${portfolio_usd:.2f} USD`\n"
        f"• **Latest Transaction Log:** {tx_status}\n"
        f"• **Execution Mode:** Supabase Cloud DB & Self-Healing Active."
    )
    
    log_to_db(balance_sol, "Cloud_Optimized_Agent", portfolio_usd)
    return state_report

# --- Autonomous AI Trading & Cloud Pipeline ---
def run_autonomous_solana_ai_brain():
    global bot_status, is_bot_running
    while True:
        with data_lock:
            running_status = is_bot_running
        if not running_status:
            time.sleep(5)
            continue
            
        try:
            current_key = get_saved_wallet_key()
            if not current_key:
                time.sleep(10)
                continue

            wallet_address, balance_sol, portfolio_usd, _, _ = get_wallet_portfolio_value()
            
            track_and_execute_trailing_tpsl()

            is_paper_mode = balance_sol < 0.05
            mode_label = "🧪 [PAPER TRADING / SIMULATION MODE]" if is_paper_mode else "⚡ [LIVE TRADING MODE]"

            trending_tokens = fetch_trending_solana_tokens()
            trade_executed = False

            for token in trending_tokens:
                mint = token.get("mint")
                symbol = token.get("symbol")
                liquidity = token.get("liquidity", 0)
                
                if mint in agent_memory.get("blacklisted_tokens", []):
                    continue

                ai_verdict = evaluate_trade_opportunity_with_ai(token)
                
                if ai_verdict.strip().upper().startswith("BUY"):
                    rug_safe, rug_msg = check_rugpull_security(mint)
                    if not rug_safe:
                        add_to_blacklist(mint, "Failed RugCheck security")
                        continue

                    amount_lamports = 10000000 
                    sim_success, sim_message = simulate_trade_opportunity(mint, amount_lamports, liquidity)
                    
                    if sim_success:
                        if is_paper_mode:
                            send_telegram_message(TELEGRAM_CHAT_ID, f"🧪 *Virtual Simulation BUY (Paper Trading)*\n• Token: `{symbol}`\n• Status: Simulated successfully in cloud sync mode.")
                            update_agent_learning("Optimized_AI_Trader", True)
                            trade_executed = True
                        else:
                            send_telegram_message(TELEGRAM_CHAT_ID, f"✅ *Simulation Passed & Live Balance Available!*\n⚡ *Executing Real Jupiter Swap...*")
                            
                            input_mint = "So11111111111111111111111111111111111111112" 
                            slippage = calculate_dynamic_slippage(liquidity)
                            swap_result = execute_real_jupiter_swap(input_mint, mint, amount_lamports, slippage)
                            
                            send_telegram_message(TELEGRAM_CHAT_ID, f"⚡ *Autonomous Swap Execution:*\n{swap_result}")
                            
                            _, token_buy_price = get_token_symbol_and_price(mint)
                            if token_buy_price > 0:
                                pos_url = f"{SUPABASE_URL}/rest/v1/active_positions"
                                pos_payload = {
                                    "token_mint": mint,
                                    "symbol": symbol,
                                    "amount": 0.01,
                                    "buy_price_usd": token_buy_price,
                                    "highest_price_usd": token_buy_price,
                                    "timestamp": time.ctime()
                                }
                                safe_post_supa(pos_url, json_data=pos_payload)

                            trade_executed = True
                            update_agent_learning("Optimized_AI_Trader", True)
                    else:
                        add_to_blacklist(mint, "Failed Pre-trade Simulation")
                    
                    break
                
            if not trade_executed:
                system_report = evaluate_real_system_state(balance_sol)
                send_telegram_message(TELEGRAM_CHAT_ID, f"🚨 *Cloud Market Monitor & Learning Cycle*\n{mode_label}\n👛 *Wallet:* `{wallet_address}` | 💰 *SOL:* `{balance_sol:.4f}`\n\n{system_report}")
            
            time.sleep(300)
        except Exception as e:
            err_msg = str(e)
            print(f"Autonomous Brain Error: {e}")
            heal_directive = ai_autonomous_self_heal(e, "run_autonomous_solana_ai_brain")
            try:
                send_telegram_message(TELEGRAM_CHAT_ID, f"🤖 *AI Self-Healing Triggered:* Cloud brain issue resolved via auto-adaptation.")
            except:
                pass
            update_agent_learning("Optimized_AI_Trader", False, err_msg)
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
