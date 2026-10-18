import time
import random
import streamlit as st
from web3 import Web3
from google import genai

# --- পেজ ডিজাইন কনফিগারেশন ---
st.set_page_config(
    page_title="AI Autonomous Crypto Bot Dashboard",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Autonomous Crypto Earning Bot & Dashboard")
st.markdown("---")

# --- সাইডবার: ওয়ালেট ও এপিআই কনফিগারেশন ---
st.sidebar.header("⚙️ Wallet & API Settings")
user_private_key = st.sidebar.text_input("Burner Wallet Private Key", type="password")
user_gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
rpc_url = st.sidebar.text_input("RPC URL", value="https://rpc-amoy.polygon.technology/")

start_button = st.sidebar.button("🚀 Start Autonomous Bot")
stop_button = st.sidebar.button("⏹ Stop Bot")

# --- মূল ড্যাশবোর্ড লেআউট (দুইটি কলাম) ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Live Wallet Status")
    wallet_status_box = st.empty()
    balance_box = st.empty()

with col2:
    st.subheader("🧠 AI Brain & Live Activity Logs")
    log_box = st.empty()

# --- এআই এজেন্ট ক্লাস ---
class DashboardAIAutonomousAgent:
    def __init__(self, private_key, rpc_url, gemini_api_key):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.wallet_address = None
        self.is_connected = False
        
        try:
            if self.w3.is_connected():
                account = self.w3.eth.account.from_key(private_key)
                self.wallet_address = account.address
                self.is_connected = True
        except:
            self.is_connected = False

        self.ai_client = genai.Client(api_key=gemini_api_key)
        self.memory_of_failures = []

    def get_wallet_balance(self):
        if not self.is_connected:
            return 0
        try:
            balance_wei = self.w3.eth.get_balance(self.wallet_address)
            return self.w3.from_wei(balance_wei, 'ether')
        except:
            return 0

    def ai_brain_decide_next_step(self, balance):
        prompt = f"""
        You are an autonomous crypto-earning AI agent.
        Current connected wallet balance: {balance} ETH/MATIC.
        Past errors encountered: {self.memory_of_failures}
        
        Suggest the next single automated task to perform. Keep it concise (under 12 words).
        """
        try:
            response = self.ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            return "Routine security check & task analysis"

    def execute_task(self, task):
        # এখানে রিয়েল অটোমেশন বা টাস্ক এক্সিকিউশন লজিক থাকবে
        success = random.choice([True, False])
        if success:
            return True, "Task completed successfully!"
        else:
            raise Exception("Task failed due to network timeout or site block.")

# --- বটের স্টেট ম্যানেজমেন্ট ---
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False

if start_button:
    if not user_private_key or not user_gemini_api_key:
        st.sidebar.error("⚠️ অনুগ্রহ করে প্রাইভেট কি এবং জেমিনি এপিআই কি উভয়ই দিন!")
    else:
        st.session_state.bot_running = True
        st.sidebar.success("বট চালু করার চেষ্টা চলছে...")

if stop_button:
    st.session_state.bot_running = False
    st.sidebar.warning("বট বন্ধ করে দেওয়া হয়েছে।")

# --- বটের মূল অপারেশন লজিক ---
if st.session_state.bot_running:
    agent = DashboardAIAutonomousAgent(user_private_key, rpc_url, user_gemini_api_key)
    
    if not agent.is_connected:
        wallet_status_box.error("❌ ভুল প্রাইভেট কি অথবা নেটওয়ার্ক কানেকশন ব্যর্থ হয়েছে।")
        st.session_state.bot_running = False
    else:
        wallet_status_box.success(f"✅ কানেক্টেড ওয়ালেট: `{agent.wallet_address}`")
        
        if 'cycle' not in st.session_state:
            st.session_state.cycle = 1
        if 'logs' not in st.session_state:
            st.session_state.logs = []

        # ব্যালেন্স চেক ও ডিসপ্লে
        balance = agent.get_wallet_balance()
        balance_box.metric(label="Current Wallet Balance", value=f"{balance} ETH/MATIC")
        
        try:
            # ১. এআই ব্রেন কাজ ঠিক করবে
            next_task = agent.ai_brain_decide_next_step(balance)
            st.session_state.logs.insert(0, f"🔄 **Cycle #{st.session_state.cycle}** | *AI Decision:* {next_task}")
            
            # ২. কাজ এক্সিকিউট করবে
            success, msg = agent.execute_task(next_task)
            st.session_state.logs.insert(0, f"✅ **Cycle #{st.session_state.cycle}** | *Status:* {msg}")
            st.session_state.cycle += 1
            
        except Exception as e:
            error_msg = str(e)
            agent.memory_of_failures.append(error_msg)
            st.session_state.logs.insert(0, f"❌ **Cycle #{st.session_state.cycle}** | *Error:* {error_msg} (AI Learning)")

        # ড্যাশবোর্ডে লাইভ লগ দেখানো
        log_box.markdown("\n\n".join(st.session_state.logs[:8]), unsafe_allow_html=True)
        
        # অটো রিলোড করার জন্য (যাতে প্রতি ১০ সেকেন্ড পর পর বট নতুন সাইকেল চালাতে পারে)
        time.sleep(10)
        st.rer()
else:
    wallet_status_box.info("ℹ️ বট বর্তমানে বন্ধ আছে। সাইডবার থেকে আপনার তথ্য দিয়ে 'Start Autonomous Bot' ক্লিক করুন।")
    balance_box.metric(label="Current Wallet Balance", value="0.0 ETH")
    log_box.text("বট স্টার্ট হলে এখানে লাইভ কার্যবিধি বা লগ দেখতে পাবেন...")