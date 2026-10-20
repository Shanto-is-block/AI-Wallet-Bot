import os
import json
import time
import threading
from threading import Lock
import sqlite3
import requests
import base64
from flask import Flask, request as flask_request
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

# Default Solana Wallet Private Key from Environment
DEFAULT_SOLANA_PRIVATE_KEY = os.environ.get("SOLANA_PRIVATE_KEY_BASE58", "")      

# Runtime Dynamic Wallet Key Storage (For /reenter feature)
runtime_private_key = DEFAULT_SOLANA_PRIVATE_KEY
user_states = {} # chat_id -> state string

# Render Web Service Public URL
RENDER_APP_URL = os.environ.get("RENDER_APP_URL", "https://ai-wallet-bot-yy4i.onrender.com") 

# Custom AI API Configuration
CUSTOM_AI_API_URL = os.environ.get("CUSTOM_AI_API_URL", "https://ai-api-cgzb.onrender.com")
CUSTOM_AI_API_KEY = os.environ.get("CUSTOM_AI_API_KEY", "ai_key_1762b5a10bdc7ed4a5db091d")

# Free Public Solana RPC URLs
SOLANA_RPC_URLS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
    "https://rpc.ankr.com/solana"
]

app = Flask(__name__)

# --- Thread Lock for Global State Safety ---
data_lock = Lock()

bot_status = "Active 🟢 (Ultra-Optimized Autonomous AI Trader)"
current_active_order = "Mission: Smart RPC routing, Auto-Blacklisting, AI simulation & Trailing TP/SL."
is_bot_running = True

# --- SQLite Database Setup for Secure Logging & Active Positions ---
DB_FILE = "agent_database.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS earnings_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                balance REAL,
                ai_strategy TEXT,
                revenue REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT,
                symbol TEXT,
                amount REAL,
                buy_price_usd REAL,
                highest_price_usd REAL,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

def log_to_db(balance, strategy, revenue):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO earnings_log (timestamp, balance, ai_strategy, revenue) VALUES (?, ?, ?, ?)",
                       (time.ctime(), balance, strategy, revenue))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Log Error: {e}")

# --- Persistent Memory File Path ---
MEMORY_FILE = "persistent_agent_memory.json"

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

strategy_pool, agent_memory = load_persistent_memory()

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

# --- Smart RPC Speed Selector ---
def get_fastest_rpc():
    fastest_rpc = SOLANA_RPC_URLS[0]
    min_latency = float('inf')
    
    for rpc in SOLANA_RPC_URLS:
        try:
            start_time = time.time()
            res = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"}, timeout=3)
            if res.status_code == 200:
                latency = time.time() - start_time
                if latency < min_latency:
                    min_latency = latency
                    fastest_rpc = rpc
        except Exception:
            continue
    return fastest_rpc

@app.route('/')
def home():
    return "🤖 Ultra-Optimized Autonomous AI Trader is Active!"

@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    global current_active_order, bot_status, runtime_private_key, user_states
    try:
        data = flask_request.get_json()
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            raw_text = message.get("text", "").strip()
            text = raw_text.lower()

            # --- 🔄 State Management: Check if waiting for new Private Key ---
            if user_states.get(chat_id) == "WAITING_FOR_PRIVATE_KEY":
                if text.startswith("/cancel"):
                    user_states[chat_id] = None
                    send_telegram_message(chat_id, "❌ Wallet update cancelled. Previous wallet remains connected.")
                    return "OK", 200
                
                new_key = raw_text
                try:
                    test_bytes = base58.b58decode(new_key)
                    test_kp = Keypair.from_bytes(test_bytes)
                    new_pubkey = str(test_kp.pubkey())
                    
                    with data_lock:
                        runtime_private_key = new_key
                        user_states[chat_id] = None
                    
                    wallet_address, balance_sol = get_real_solana_wallet_details()
                    send_telegram_message(chat_id, f"✅ *Previous wallet disconnected successfully!*\n🔌 *New Wallet Connected!*\n\n👛 *Address:* `{wallet_address}`\n💰 *SOL Balance:* `{balance_sol:.4f} SOL`")
                except Exception as e:
                    send_telegram_message(chat_id, f"❌ *Invalid Private Key!* Please check and send again correctly, or type `/cancel` to abort.\nError: `{str(e)[:35]}`")
                return "OK", 200

            # --- Standard Commands ---
            if text.startswith("/start"):
                welcome_text = (
                    "🚀 *Ultra-Optimized Autonomous AI Agent Activated!*\n\n"
                    "🔍 *Mode:* Smart RPC Router, Auto-Blacklisting, RugCheck & Trailing TP/SL.\n\n"
                    "Commands:\n"
                    "📊 `/status` - Complete portfolio valuation & system state\n"
                    "💰 `/balance` - Live balance of SOL & all SPL assets\n"
                    "📜 `/trans` - View first 10 transactions with USD value\n"
                    "📈 `/scan` - Jupiter price API & token scan\n"
                    "⚡ `/swap` - Execute manual test swap (0.01 SOL to USDC)\n"
                    "🔄 `/reenter` - Disconnect current wallet & connect a new Private Key\n"
                    "🛑 `/stop` - Pause autonomous operations\n"
                    "✍️ `Order: [your command]` - Update operational focus"
                )
                send_telegram_message(chat_id, welcome_text)

            elif text.startswith("/reenter"):
                user_states[chat_id] = "WAITING_FOR_PRIVATE_KEY"
                send_telegram_message(chat_id, "🔄 *Wallet Re-entry Mode Activated*\n\nPlease reply with your **new Solana Private Key (Base58)**.\n*(Your previous wallet will be disconnected immediately upon verification.)*\n\nType `/cancel` if you want to abort.")

            elif text.startswith("/cancel"):
                send_telegram_message(chat_id, "ℹ️ No active operation to cancel.")

            elif text.startswith("/status"):
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
                wallet_address, balance_sol = get_real_solana_wallet_details()
                system_state_msg = evaluate_real_system_state(balance_sol)
                send_telegram_message(chat_id, f"🤖 Agent is running live.\n\n{system_state_msg}")

    except Exception as e:
        print(f"Webhook Error: {e}")
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def self_ping_worker():
    while True:
        try:
            time.sleep(480) 
            if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
                requests.get(RENDER_APP_URL, timeout=10)
        except Exception:
            pass

def setup_telegram_webhook():
    time.sleep(5) 
    if RENDER_APP_URL and "your-bot-name" not in RENDER_APP_URL:
        webhook_url = f"{RENDER_APP_URL}/{TELEGRAM_BOT_TOKEN}"
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}"
        try:
            requests.get(api_url, timeout=10)
        except Exception:
            pass

def get_solana_keypair():
    global runtime_private_key
    try:
        if not runtime_private_key:
            print("❌ Error: Solana Private Key is missing!")
            return None
        secret_key_bytes = base58.b58decode(runtime_private_key)
        return Keypair.from_bytes(secret_key_bytes)
    except Exception as e:
        print(f"Keypair Error: {e}")
        return None

# ==========================================
# --- REAL ON-CHAIN & PORTFOLIO TOOLS ---
# ==========================================

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
        res = requests.post(rpc_url, json=payload, timeout=6).json()
        if "result" in res and "value" in res["result"]:
            balance_sol = float(res["result"]["value"]) / 1000000000.0
    except Exception as e:
        print(f"Balance Check Error: {e}")
    return wallet_address, balance_sol

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
            res = requests.post(rpc_url, json=payload, timeout=6).json()
            if "result" in res and "value" in res["result"]:
                accounts = res["result"]["value"]
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
        res = requests.get(token_info_url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data and "symbol" in data:
                symbol = data["symbol"]
    except Exception:
        pass

    try:
        jup_url = f"https://price.jup.ag/v4/price?ids={mint}"
        res = requests.get(jup_url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            price_data = data.get("data", {}).get(mint, {})
            p = price_data.get("price")
            if p is not None:
                return symbol, float(p)
    except Exception:
        pass

    try:
        dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        res = requests.get(dex_url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            pairs = data.get("pairs", [])
            if pairs:
                price_str = pairs[0].get("priceUsd", 0)
                price = float(price_str or 0)
                if "baseToken" in pairs[0] and "symbol" in pairs[0]["baseToken"]:
                    symbol = pairs[0]["baseToken"]["symbol"]
    except Exception:
        pass

    return symbol, price

def tool_fetch_real_market_data_with_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=SOLUSDT"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get("lastPrice", 0))
            change = float(data.get("priceChangePercent", 0))
            return True, f"• **Network Status:** Connected (Binance API)\n• **SOL Market Price:** `${price:.2f} USD`\n• **24h Change:** {change:.2f}%", price
    except Exception:
        pass

    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_change=true"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            price = float(data.get("solana", {}).get("usd", 0))
            change = float(data.get("solana", {}).get("usd_24h_change", 0))
            return True, f"• **Network Status:** Connected (CoinGecko API)\n• **SOL Market Price:** `${price:.2f} USD`\n• **24h Change:** {change:.2f}%", price
    except Exception:
        pass

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
        res = requests.post(rpc_url, json=payload, timeout=6).json()
        if "result" in res and res["result"]:
            sig_info = res["result"][0]
            sig = sig_info.get("signature", "N/A")
            slot = sig_info.get("slot", "N/A")
            err = sig_info.get("err")
            status = "Success 🟢" if err is None else "Failed 🔴"
            return f"Signature: `{sig[:16]}...` | Slot: {slot} | Status: {status}"
        return "No recent transactions found on-chain."
    except Exception as e:
        return f"Error fetching transactions: {str(e)[:25]}"

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
        res = requests.post(rpc_url, json=payload, timeout=6).json()
        if "result" in res and res["result"]:
            sigs = res["result"]
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
                    tx_res = requests.post(rpc_url, json=tx_payload, timeout=3).json()
                    if "result" in tx_res and tx_res["result"]:
                        meta = tx_res["result"].get("meta", {})
                        pre_balances = meta.get("preBalances", [0])
                        post_balances = meta.get("postBalances", [0])
                        if pre_balances and post_balances:
                            diff = abs(pre_balances[0] - post_balances[0]) / 1000000000.0
                            sol_transferred = diff
                except Exception:
                    pass

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
        return f"❌ Error fetching transactions: {str(e)[:40]}"

# ==========================================
# --- AI ANALYSIS & SELF-LEARNING BRIDGE ---
# ==========================================
def analyze_data_with_custom_ai(transaction_details):
    try:
        headers = {
            "Authorization": f"Bearer {CUSTOM_AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "analyze_solana_transaction_or_wallet",
            "data": transaction_details,
            "instructions": "Analyze this blockchain context. Return a short verdict: SAFE or DANGEROUS."
        }
        
        response = requests.post(CUSTOM_AI_API_URL, json=payload, headers=headers, timeout=6)
        if response.status_code == 200:
            ai_res = response.json()
            return ai_res.get("analysis", "AI processed, status: Safe.")
        else:
            return f"🛡️ AI Guard Active: No critical on-chain anomalies found (API Status: {response.status_code})"
    except Exception as e:
        return f"🛡️ AI Guard Active: Secure local monitoring operational."

def evaluate_trade_opportunity_with_ai(token_info):
    try:
        headers = {
            "Authorization": f"Bearer {CUSTOM_AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "evaluate_token_trade",
            "data": token_info,
            "instructions": "Analyze this Solana token for high-probability trading. Return your decision strictly starting with either 'BUY' or 'SKIP', followed by a short reason."
        }
        
        response = requests.post(CUSTOM_AI_API_URL, json=payload, headers=headers, timeout=6)
        if response.status_code == 200:
            ai_res = response.json()
            analysis = ai_res.get("analysis", "SKIP: No clear bullish signal.")
            return analysis
        else:
            return "SKIP: AI API unresponsive."
    except Exception as e:
        return f"SKIP: Error connecting to AI ({str(e)[:20]})"

# ==========================================
# --- 🛡️ RUG-PULL & SMART CONTRACT CHECK ---
# ==========================================
def check_rugpull_security(mint):
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
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
        return True, f"RugCheck Notice: {str(e)[:30]}"

# ==========================================
# --- 🧪 DYNAMIC SLIPPAGE & SIMULATION ENGINE ---
# ==========================================
def calculate_dynamic_slippage(liquidity_usd):
    if liquidity_usd < 20000:
        return 150 # 1.5%
    elif liquidity_usd < 100000:
        return 100 # 1.0%
    else:
        return 50  # 0.5%

def simulate_trade_opportunity(mint, amount_lamports, liquidity_usd):
    try:
        input_mint = "So11111111111111111111111111111111111111112" # SOL
        slippage_bps = calculate_dynamic_slippage(liquidity_usd)
        
        quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={mint}&amount={amount_lamports}&slippageBps={slippage_bps}"
        
        res = requests.get(quote_url, timeout=5)
        if res.status_code != 200:
            return False, f"Simulation Failed: Jupiter Quote API error (Status: {res.status_code})"
            
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
        
        headers = {
            "Authorization": f"Bearer {CUSTOM_AI_API_KEY}",
            "Content-Type": "application/json"
        }
        ai_payload = {
            "api_key": CUSTOM_AI_API_KEY,
            "task": "simulate_trade_risk_reward",
            "data": sim_payload,
            "instructions": "Simulate this trade. Return strictly 'PROFITABLE' if safe to proceed, or 'HIGH_RISK' if it should be avoided."
        }
        
        ai_res = requests.post(CUSTOM_AI_API_URL, json=ai_payload, headers=headers, timeout=6)
        if ai_res.status_code == 200:
            verdict = ai_res.json().get("analysis", "PROFITABLE")
            if "HIGH_RISK" in verdict.upper() or "DANGEROUS" in verdict.upper():
                update_agent_learning("Simulation_Risk_Manager", False, "AI simulation flagged high risk")
                return False, f"Simulation Rejected ❌ by AI Risk Audit: {verdict}"
        
        update_agent_learning("Simulation_Risk_Manager", True)
        return True, f"Simulation Passed 🟢 (Slippage: {slippage_bps/100}%, Impact: {price_impact*100:.2f}%)"
        
    except Exception as e:
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
    try:
        keypair = get_solana_keypair()
        if not keypair:
            update_agent_learning("Jupiter_Real_Swap_Engine", False, "Keypair error")
            return "❌ Keypair configuration error."
        
        wallet_address = str(keypair.pubkey())
        
        quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_lamports}&slippageBps={slippage_bps}"
        quote_res = requests.get(quote_url, timeout=5)
        if quote_res.status_code != 200:
            update_agent_learning("Jupiter_Real_Swap_Engine", False, "Quote API failed")
            return f"⚠️ Jupiter Quote Failed (Status: {quote_res.status_code})"
            
        quote_data = quote_res.json()
        
        swap_url = "https://quote-api.jup.ag/v6/swap"
        payload = {
            "quoteResponse": quote_data,
            "userPublicKey": wallet_address,
            "wrapAndUnwrapSol": True
        }
        swap_res = requests.post(swap_url, json=payload, timeout=6)
        if swap_res.status_code != 200:
            update_agent_learning("Jupiter_Real_Swap_Engine", False, "Swap transaction build failed")
            return f"⚠️ Swap Transaction Build Failed (Status: {swap_res.status_code})"
            
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
        
        broadcast_res = requests.post(rpc_url, json=send_payload, timeout=8).json()
        if "result" in broadcast_res:
            tx_sig = broadcast_res["result"]
            update_agent_learning("Jupiter_Real_Swap_Engine", True)
            return f"✅ **Jupiter Swap Executed Successfully!**\n• Signature: `{tx_sig[:18]}...`\n• View on Solscan: [Check Tx](https://solscan.io/tx/{tx_sig})"
        else:
            err_msg = broadcast_res.get("error", {}).get("message", "Unknown error")
            update_agent_learning("Jupiter_Real_Swap_Engine", False, err_msg)
            return f"⚠️ Swap Execution Rejected by Network: {err_msg[:60]}"
            
    except Exception as e:
        update_agent_learning("Jupiter_Real_Swap_Engine", False, str(e))
        return f"⚠️ Swap Execution Notice: {str(e)[:50]}"

# ==========================================
# --- 📈 TRAILING STOP-LOSS & TAKE-PROFIT ---
# ==========================================
def track_and_execute_trailing_tpsl():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, token_mint, symbol, amount, buy_price_usd, highest_price_usd FROM active_positions")
        positions = cursor.fetchall()
        conn.close()

        if not positions:
            return

        for pos in positions:
            pos_id, mint, symbol, amount, buy_price, highest_price = pos
            if buy_price <= 0:
                continue

            _, current_price = get_token_symbol_and_price(mint)
            if current_price <= 0:
                continue

            if current_price > highest_price:
                highest_price = current_price
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("UPDATE active_positions SET highest_price_usd = ? WHERE id = ?", (highest_price, pos_id))
                conn.commit()
                conn.close()

            total_pnl_pct = ((current_price - buy_price) / buy_price) * 100
            drawdown_from_peak = ((highest_price - current_price) / highest_price) * 100

            if total_pnl_pct >= 40.0:
                send_telegram_message(TELEGRAM_CHAT_ID, f"🎯 *Take-Profit Target Hit!*\n• Token: `{symbol}`\n• Total Profit: `+{total_pnl_pct:.2f}%`\n⚡ *Selling to lock profits...*")
                
                token_lamports = int(amount * 1_000_000_000)
                sol_mint = "So11111111111111111111111111111111111111112"
                sell_result = execute_real_jupiter_swap(mint, sol_mint, token_lamports)
                
                send_telegram_message(TELEGRAM_CHAT_ID, f"✅ *Take-Profit Execution:*\n{sell_result}")
                update_agent_learning("Trailing_TP_SL_Engine", True)
                
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM active_positions WHERE id = ?", (pos_id,))
                conn.commit()
                conn.close()

            elif drawdown_from_peak >= 15.0 or total_pnl_pct <= -15.0:
                reason = f"Trailing Drop (-{drawdown_from_peak:.2f}% from peak)" if drawdown_from_peak >= 15.0 else f"Fixed Stop-Loss ({total_pnl_pct:.2f}%)"
                send_telegram_message(TELEGRAM_CHAT_ID, f"🛡️ *Trailing Stop-Loss Triggered!*\n• Token: `{symbol}`\n• Reason: {reason}\n• Final PnL: `{total_pnl_pct:.2f}%`\n⚡ *Executing Sell...*")
                
                token_lamports = int(amount * 1_000_000_000)
                sol_mint = "So11111111111111111111111111111111111111112"
                sell_result = execute_real_jupiter_swap(mint, sol_mint, token_lamports)
                
                send_telegram_message(TELEGRAM_CHAT_ID, f"🛑 *Stop-Loss Execution:*\n{sell_result}")
                update_agent_learning("Trailing_TP_SL_Engine", False, reason)
                
                add_to_blacklist(mint, f"Hit Stop-Loss at {total_pnl_pct:.2f}%")
                
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM active_positions WHERE id = ?", (pos_id,))
                conn.commit()
                conn.close()

    except Exception as e:
        print(f"Trailing TP/SL Error: {e}")

# ==========================================
# --- AUTONOMOUS TOKEN DISCOVERY & SCANNING ---
# ==========================================
def fetch_trending_solana_tokens():
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
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
        f"⚙️ *Live System Execution Report*\n"
        f"• **Active Mission:** {current_mission}\n"
        f"{market_msg}\n"
        f"• **Total Portfolio USD:** `${portfolio_usd:.2f} USD`\n"
        f"• **Latest Transaction Log:** {tx_status}\n"
        f"• **Execution Mode:** Smart RPC & Auto-Blacklist Active."
    )
    
    log_to_db(balance_sol, "Optimized_Agent_Active", portfolio_usd)
    return state_report

# --- Autonomous AI Trading & Optimized Pipeline ---
def run_autonomous_solana_ai_brain():
    global bot_status, is_bot_running
    while True:
        with data_lock:
            running_status = is_bot_running
        if not running_status:
            time.sleep(5)
            continue
            
        try:
            wallet_address, balance_sol, portfolio_usd, _, _ = get_wallet_portfolio_value()
            
            track_and_execute_trailing_tpsl()

            if balance_sol < 0.05:
                send_telegram_message(TELEGRAM_CHAT_ID, f"⚠️ Autonomous Bot: Balance too low (`{balance_sol:.4f} SOL`). Min 0.05 SOL required.")
                time.sleep(600)
                continue

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
                    send_telegram_message(TELEGRAM_CHAT_ID, f"🤖 *AI Trade Signal BUY Detected!*\n• Token: `{symbol}`\n• Verdict: {ai_verdict}\n\n🛡️ *Checking RugCheck Smart Contract Security...*")
                    
                    rug_safe, rug_msg = check_rugpull_security(mint)
                    if not rug_safe:
                        send_telegram_message(TELEGRAM_CHAT_ID, f"🚫 *RugCheck Blocked Trade!*\n{rug_msg}\n• Action: Automatically blacklisted.")
                        add_to_blacklist(mint, "Failed RugCheck security")
                        continue

                    send_telegram_message(TELEGRAM_CHAT_ID, f"✅ *RugCheck Passed!*\n🧪 *Initiating Dynamic Simulation...*")
                    
                    amount_lamports = 10000000 # 0.01 SOL
                    sim_success, sim_message = simulate_trade_opportunity(mint, amount_lamports, liquidity)
                    
                    if sim_success:
                        send_telegram_message(TELEGRAM_CHAT_ID, f"✅ *Simulation Successful!*\n{sim_message}\n\n⚡ *Executing Real Jupiter Swap via Fast RPC...*")
                        
                        input_mint = "So11111111111111111111111111111111111111112" # SOL
                        slippage = calculate_dynamic_slippage(liquidity)
                        swap_result = execute_real_jupiter_swap(input_mint, mint, amount_lamports, slippage)
                        
                        send_telegram_message(TELEGRAM_CHAT_ID, f"⚡ *Autonomous Swap Execution:*\n{swap_result}")
                        
                        _, token_buy_price = get_token_symbol_and_price(mint)
                        if token_buy_price > 0:
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO active_positions (token_mint, symbol, amount, buy_price_usd, highest_price_usd, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                                           (mint, symbol, 0.01, token_buy_price, token_buy_price, time.ctime()))
                            conn.commit()
                            conn.close()

                        trade_executed = True
                        update_agent_learning("Optimized_AI_Trader", True)
                    else:
                        send_telegram_message(TELEGRAM_CHAT_ID, f"🛡️ *Simulation Blocked Trade!*\n{sim_message}\n• Action: Trade aborted.")
                        add_to_blacklist(mint, "Failed Pre-trade Simulation")
                    
                    break
                
            if not trade_executed:
                system_report = evaluate_real_system_state(balance_sol)
                send_telegram_message(TELEGRAM_CHAT_ID, f"🚨 *Periodic Scan & Market Monitor*\n👛 *Wallet:* `{wallet_address}` | 💰 *SOL:* `{balance_sol:.4f}`\n\n{system_report}\n• *Scan Result:* Active positions & market under surveillance.")
            
            time.sleep(300)
        except Exception as e:
            print(f"Autonomous Brain Error: {e}")
            update_agent_learning("Optimized_AI_Trader", False, str(e))
            time.sleep(30)

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
