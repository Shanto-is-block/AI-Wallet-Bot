import os
import time
import threading
import requests
import hashlib
streamlit as st
from web3 import Web3
from google import genai

# Streamlit Page Configuration
st.set_page_config(
    page_title="AI Autonomous Crypto Earning Bot",
    page_icon="🤖",
    layout="wide"
)

# Initialize Session States
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'user_uid' not in st.session_state:
    st.session_state.user_uid = ""

if 'bot_initialized' not in st.session_state:
    st.session_state.bot_initialized = False

if 'ping_bot_running' not in st.session_state:
    st.session_state.ping_bot_running = False

if 'logs' not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.logs.insert(0, f"[{timestamp}] {message}")

# Telegram Sender Function
def send_telegram_message(token, chat_id, message):
    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            pass

# --- Sidebar: Login & Authentication Section ---
st.sidebar.title("🔐 User Login & Session")

if not st.session_state.logged_in:
    st.sidebar.markdown("আপনার ওয়ালেট প্রাইভেট কি এবং জেমিনি এপিআই দিয়ে লগইন করুন:")
    login_private_key = st.sidebar.text_input("Burner Wallet Private Key", type="password", key="login_pk")
    login_gemini_key = st.sidebar.text_input("Gemini API Key", type="password", key="login_gk")
    
    if st.sidebar.button("🔑 Sign In / Generate UID"):
        if login_private_key and login_gemini_key:
            # Generate a unique UID based on credentials hash
            raw_string = login_private_key + login_gemini_key
            uid = "UID-" + hashlib.sha256(raw_string.encode()).hexdigest()[:10].upper()
            
            st.session_state.logged_in = True
            st.session_state.user_uid = uid
            st.session_state.saved_pk = login_private_key
            st.session_state.saved_gk = login_gemini_key
            st.sidebar.success(f"সফলভাবে লগইন হয়েছে! আপনার UID: {uid}")
            st.rerun()
        else:
            st.sidebar.error("দয়া করে উভয় ফিল্ড পূরণ করুন।")
else:
    st.sidebar.success(f"লগইন করা আছে!")
    st.sidebar.info(f"ইউজার আইডি (UID):\n**{st.session_state.user_uid}**")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_uid = ""
        st.session_state.bot_initialized = False
        st.rerun()

# --- Main Dashboard (Only accessible if logged in) ---
if st.session_state.logged_in:
    st.title(f"🤖 Autonomous Bot Dashboard (User: {st.session_state.user_uid})")
    st.markdown("---")

    # Additional Controls in Sidebar for Bot Operations
    st.sidebar.markdown("---")
    st.sidebar.title("⚙️ Bot Configurations")
    rpc_url_input = st.sidebar.text_input("RPC URL", value="https://rpc-amoy.polygon.technology/")

    st.sidebar.markdown("---")
    st.sidebar.title("🤖 Telegram Keep-Alive Bot")
    telegram_token_input = st.sidebar.text_input("Telegram Bot Token", type="password")
    telegram_chat_id_input = st.sidebar.text_input("Telegram Chat ID", type="password")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Live Wallet Status")
        wallet_status_placeholder = st.empty()
        wallet_status_placeholder.info(f"সক্রিয় ইউজার আইডি: {st.session_state.user_uid}")

    with col2:
        st.subheader("🧠 AI Brain & Live Activity Logs")
        log_placeholder = st.empty()

    # Background Worker 1: Crypto Earning Bot
    def run_autonomous_bot(private_key, gemini_key, rpc_url):
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                add_log("❌ নেটওয়ার্ক কানেকশন ব্যর্থ হয়েছে।")
                return

            account = w3.eth.account.from_key(private_key)
            add_log(f"✅ সফলভাবে ওয়ালেট কানেক্ট হয়েছে: {account.address[:6]}...{account.address[-4:]}")

            client = genai.Client(api_key=gemini_key)
            add_log("🤖 জেমিনি এআই ব্রেন একটিভ করা হয়েছে।")

            while True:
                balance_wei = w3.eth.get_balance(account.address)
                balance_eth = w3.from_wei(balance_wei, 'ether')
                add_log(f"💰 বর্তমান ব্যালেন্স: {balance_eth} MATIC")

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents="Analyze current micro-task environment for automated web3 execution and give a short action status."
                )
                add_log(f"🧠 এআই সিদ্ধান্ত: {response.text.strip()}")

                time.sleep(300) # প্রতি ৫ মিনিট পরপর রান হবে

        except Exception as e:
            add_log(f"❌ এরর দেখা দিয়েছে: {str(e)}")

    # Background Worker 2: Keep-Alive Ping Bot
    def run_keep_alive_bot(token, chat_id):
        add_log("🔄 টেলিগ্রাম কিপ-অ্যালাইভ বট ব্যাকগ্রাউন্ডে চালু হয়েছে।")
        while True:
            try:
                ping_msg = f"🟢 সার্ভার একটিভ আছে [UID: {st.session_state.user_uid}]"
                send_telegram_message(token, chat_id, ping_msg)
            except Exception:
                pass
            time.sleep(600)

    # Start Crypto Bot Button
    if st.sidebar.button("🚀 Start Autonomous Bot"):
        if not st.session_state.bot_initialized:
            add_log("ক্রিপ্টো বট ব্যাকগ্রাউন্ডে চালু করা হচ্ছে...")
            bot_thread = threading.Thread(
                target=run_autonomous_bot,
                args=(st.session_state.saved_pk, st.session_state.saved_gk, rpc_url_input),
                daemon=True
            )
            bot_thread.start()
            st.session_state.bot_initialized = True
            st.sidebar.success("ক্রিপ্টো বট রান করছে!")
        else:
            st.sidebar.info("ক্রিপ্টো বট ইতোমধ্যে চালু আছে।이")

    # Start Keep-Alive Telegram Bot Button
    if st.sidebar.button("🔔 Start Telegram Keep-Alive"):
        if not telegram_token_input or not telegram_chat_id_input:
            st.sidebar.error("দয়া করে টেলিগ্রাম টোকেন ও চ্যাট আইডি দিন।")
        else:
            if not st.session_state.ping_bot_running:
                ping_thread = threading.Thread(
                    target=run_keep_alive_bot,
                    args=(telegram_token_input, telegram_chat_id_input),
                    daemon=True
                )
                ping_thread.start()
                st.session_state.ping_bot_running = True
                st.sidebar.success("টেলিগ্রাম কিপ-অ্যালাইভ বট চালু হয়েছে!")
            else:
                st.sidebar.info("কিপ-অ্যালাইভ বট ইতোমধ্যে চালু আছে।")

    # Render dynamic logs on UI
    with log_placeholder.container():
        if st.session_state.logs:
            for log in st.session_state.logs[:15]:
                st.write(log)
        else:
            st.info("এখনো কোনো লগ তৈরি হয়নি। বট চালু করতে সাইডবারের স্টার্ট বাটনে ক্লিক করুন।")
else:
    st.info("👋 দয়া করে সাইডবার থেকে আপনার **Wallet Private Key** এবং **Gemini API Key** দিয়ে সাইন ইন (Sign In) করুন এবং আপনার ইউনিক ইউজার আইডি (UID) generate করুন।")
