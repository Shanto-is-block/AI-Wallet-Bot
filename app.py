import os
import time
import threading
import requests
import streamlit as st
from web3 import Web3
from google import genai

# Streamlit Page Configuration
st.set_page_config(
    page_title="AI Autonomous Crypto Earning Bot",
    page_icon="🤖",
    layout="wide"
)

# Use Global state for persistent background worker across sessions
if 'bot_initialized' not in st.session_state:
    st.session_state.bot_initialized = False

if 'logs' not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.logs.insert(0, f"[{timestamp}] {message}")

# Telegram Notification Function
def send_telegram_message(message):
    # আপনার টেলিগ্রাম বট টোকেন এবং চ্যাট আইডি এখানে বসিয়ে দিন
    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"
    
    if TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            pass

# Sidebar Configuration for Credentials
st.sidebar.title("⚙️ Wallet & API Settings")
private_key_input = st.sidebar.text_input("Burner Wallet Private Key", type="password")
gemini_key_input = st.sidebar.text_input("Gemini API Key", type="password")
rpc_url_input = st.sidebar.text_input("RPC URL", value="https://rpc-amoy.polygon.technology/")

# Main Dashboard UI
st.title("🤖 AI Autonomous Crypto Earning Bot & Dashboard")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Live Wallet Status")
    wallet_status_placeholder = st.empty()

with col2:
    st.subheader("🧠 AI Brain & Live Activity Logs")
    log_placeholder = st.empty()

# Background Bot Loop Logic that runs independently
def run_autonomous_bot(private_key, gemini_key, rpc_url):
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            add_log("❌ নেটওয়ার্ক কানেকশন ব্যর্থ হয়েছে।")
            send_telegram_message("❌ ক্রিপ্টো বট: নেটওয়ার্ক কানেকশন ব্যর্থ হয়েছে!")
            return

        account = w3.eth.account.from_key(private_key)
        add_log(f"✅ সফলভাবে ওয়ালেট কানেক্ট হয়েছে: {account.address[:6]}...{account.address[-4:]}")
        send_telegram_message(f"✅ ক্রিপ্টো বট সফলভাবে কানেক্ট হয়েছে!\nঅ্যাড্রেস: {account.address}")

        client = genai.Client(api_key=gemini_key)
        add_log("🤖 জেমিনি এআই ব্রেন একটিভ করা হয়েছে।")

        # Continuous loop running in background daemon thread
        while True:
            balance_wei = w3.eth.get_balance(account.address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            log_msg = f"💰 বর্তমান ব্যালেন্স: {balance_eth} MATIC"
            add_log(log_msg)

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="Analyze current micro-task environment for automated web3 execution and give a short action status."
            )
            ai_msg = f"🧠 এআই সিদ্ধান্ত: {response.text.strip()}"
            add_log(ai_msg)

            # টেলিগ্রামে প্রতি লুপে আপডেট পাঠানো (সার্ভার সচল রাখতেও সাহায্য করবে)
            send_telegram_message(f"{log_msg}\n{ai_msg}")

            time.sleep(300) # প্রতি ৫ মিনিট পর পর চেক করবে এবং টেলিগ্রামে জানাবে

    except Exception as e:
        err_msg = f"❌ এরর দেখা দিয়েছে: {str(e)}"
        add_log(err_msg)
        send_telegram_message(err_msg)

# Start Bot Trigger Button
if st.sidebar.button("🚀 Start Autonomous Bot"):
    if not private_key_input or not gemini_key_input:
        st.sidebar.error("দয়া করে প্রাইভেট কি এবং জেমিনি এপিআই কি দিন।")
    else:
        if not st.session_state.bot_initialized:
            add_log("বট ব্যাকগ্রাউন্ডে চালু করা হচ্ছে...")
            bot_thread = threading.Thread(
                target=run_autonomous_bot,
                args=(private_key_input, gemini_key_input, rpc_url_input),
                daemon=True
            )
            bot_thread.start()
            st.session_state.bot_initialized = True
            st.sidebar.success("বট সফলভাবে ব্যাকগ্রাউন্ডে রান করছে!")
        else:
            st.sidebar.info("বট ইতোমধ্যে চালিত অবস্থায় আছে।")

# Render dynamic logs on UI
with log_placeholder.container():
    if st.session_state.logs:
        for log in st.session_state.logs[:15]:
            st.write(log)
    else:
        st.info("এখনো কোনো লগ তৈরি হয়নি। বট চালু করতে সাইডবারের স্টার্ট বাটনে ক্লিক করুন।")
