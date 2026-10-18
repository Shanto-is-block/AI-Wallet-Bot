import os
import time
import threading
import streamlit as st
from web3 import Web3
from google import genai

# Streamlit Page Configuration
st.set_page_config(
    page_title="AI Autonomous Crypto Earning Bot",
    page_icon="🤖",
    layout="wide"
)

# Initialize Session State variables for Bot Control
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'logs' not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.logs.insert(0, f"[{timestamp}] {message}")

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

# Bot Control Buttons
if st.sidebar.button("🚀 Start Autonomous Bot"):
    if not private_key_input or not gemini_key_input:
        st.sidebar.error("দয়া করে প্রাইভেট কি এবং জেমিনি এপিআই কি দিন।")
    else:
        st.session_state.bot_running = True
        add_log("বট চালু করার চেষ্টা চলছে...")

if st.sidebar.button("⏹️ Stop Bot"):
    st.session_state.bot_running = False
    add_log("বট বন্ধ করে দেওয়া হয়েছে।")

# Background Bot Loop Logic
def run_autonomous_bot(private_key, gemini_key, rpc_url):
    try:
        # Initialize Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            add_log("❌ নেটওয়ার্ক কানেকশন ব্যর্থ হয়েছে।")
            st.session_state.bot_running = False
            return

        account = w3.eth.account.from_key(private_key)
        add_log(f"✅ সফলভাবে ওয়ালেট কানেক্ট হয়েছে: {account.address[:6]}...{account.address[-4:]}")

        # Initialize Gemini Client using google-genai
        client = genai.Client(api_key=gemini_key)
        add_log("🤖 জেমিনি এআই ব্রেন একটিভ করা হয়েছে।")

        while st.session_state.bot_running:
            # Check Balance
            balance_wei = w3.eth.get_balance(account.address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            add_log(f"💰 বর্তমান ব্যালেন্স: {balance_eth} MATIC")

            # AI Decision Making Simulation via Gemini
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="Analyze current micro-task environment for automated web3 execution and give a short action status."
            )
            add_log(f"🧠 এআই সিদ্ধান্ত: {response.text.strip()}")

            time.sleep(10) # Wait before next loop iteration

    except Exception as e:
        add_log(f"❌ এরর দেখা দিয়েছে: {str(e)}")
        st.session_state.bot_running = False

# Trigger background thread if bot is started
if st.session_state.bot_running:
    if 'bot_thread' not in st.session_state or not st.session_state.bot_thread.is_alive():
        st.session_state.bot_thread = threading.Thread(
            target=run_autonomous_bot,
            args=(private_key_input, gemini_key_input, rpc_url_input),
            daemon=True
        )
        st.session_state.bot_thread.start()

# Render dynamic logs on UI
with log_placeholder.container():
    if st.session_state.logs:
        for log in st.session_state.logs[:15]:
            st.write(log)
    else:
        st.info("বট বন্ধ আছে অথবা এখনো কোনো লগ তৈরি হয়নি।")

# Refresh UI periodically when running
if st.session_state.bot_running:
    time.sleep(2)
    st.rerun()
