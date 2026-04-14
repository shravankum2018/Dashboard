import streamlit as st
import requests
import json
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)
ENCTOKEN = os.getenv("ENCTOKEN", "")
USER_ID  = os.getenv("ZERODHA_USER_ID", "")
PASSWORD = os.getenv("ZERODHA_PASSWORD", "")

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Zerodha Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Enable built-in selectbox search
st.config.set_option("deprecation.showPyplotGlobalUse", False)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Reset & Base */
.stApp {
    background: #0a0c10;
}

.block-container {
    padding: 1.5rem 2rem !important;
    max-width: 1200px !important;
}

/* Hide Streamlit branding */
#MainMenu, footer, header, .stDeployButton {
    display: none !important;
}

/* Typography */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Headers */
.main-header {
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, #00e5a0 0%, #00b8ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
}

.sub-header {
    font-size: 0.75rem;
    color: #4a5060;
    margin-bottom: 1rem;
}

/* Section styling */
.section-card {
    background: #111318;
    border: 1px solid #1e2128;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}

.section-title {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #4a5060;
    margin-bottom: 0.5rem;
}

/* Input styling */
.stSelectbox [data-baseweb="select"] {
    background-color: #0a0c10;
    border-color: #1e2128;
}

.stNumberInput input, .stTextInput input {
    background-color: #0a0c10 !important;
    border-color: #1e2128 !important;
    color: #e8eaf0 !important;
}

/* Button styling */
.stButton button {
    font-weight: 600 !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease !important;
    white-space: nowrap !important;
}

/* Primary action button */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #00e5a0 0%, #00b8ff 100%) !important;
    color: #000 !important;
}

/* Secondary buttons */
.stButton button[kind="secondary"] {
    background: #1e2128 !important;
    color: #e8eaf0 !important;
    border: 1px solid #2a3040 !important;
}

.stButton button[kind="secondary"]:hover {
    background: #2a3040 !important;
}

/* Metrics */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin-top: 0.75rem;
}

.metric-card {
    background: #0a0c10;
    border: 1px solid #1e2128;
    border-radius: 8px;
    padding: 0.75rem;
    text-align: center;
}

.metric-label {
    font-size: 0.65rem;
    color: #4a5060;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}

.metric-value {
    font-size: 1.2rem;
    font-weight: 700;
    color: #00e5a0;
}

.metric-value.red {
    color: #ff4d6d;
}

/* Info box */
.info-box {
    background: rgba(0,229,160,0.05);
    border-left: 3px solid #00e5a0;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    margin: 0.75rem 0;
    font-size: 0.85rem;
}

/* Log */
.log-container {
    background: #0a0c10;
    border: 1px solid #1e2128;
    border-radius: 8px;
    padding: 0.75rem;
    max-height: 150px;
    overflow-y: auto;
    font-size: 0.75rem;
    font-family: monospace;
}

.log-entry {
    padding: 0.25rem 0;
    border-bottom: 1px solid #1e2128;
    color: #8890a0;
}

.log-success {
    color: #00e5a0;
}

.log-error {
    color: #ff4d6d;
}

/* Expander */
.streamlit-expanderHeader {
    background: #111318 !important;
    border-radius: 8px !important;
}

/* Divider */
hr {
    border-color: #1e2128;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL = 'https://kite.zerodha.com'
LOGIN_URL = f'{BASE_URL}/api/login'
TWOFA_URL = f'{BASE_URL}/api/twofa'
ORDER_URL = f'{BASE_URL}/oms/orders'
HIST_URL = f'{BASE_URL}/oms/instruments/historical/{{instrument_id}}/{{interval}}'

TOKEN_CSV = r"C:\Users\harsh\Dropbox\Trading_2026\Dashboard\symbol_data\token_ids.csv"

@st.cache_data
def load_token_map(path: str = TOKEN_CSV):
    if not os.path.exists(path):
        st.error(f"❌ Token file not found: {path}")
        st.stop()
    df = pd.read_csv(path, dtype={"symbol": str, "token": int})
    df.columns = df.columns.str.strip().str.lower()
    token_dict = dict(zip(df["symbol"], df["token"]))
    return sorted(token_dict.keys()), token_dict

SYMBOLS, TOKEN_MAP = load_token_map()

# ─── Session State ────────────────────────────────────────────────────────────

if "enctoken" not in st.session_state:
    st.session_state.enctoken = ENCTOKEN
if "user_id" not in st.session_state:
    st.session_state.user_id = USER_ID
if "auto_login_done" not in st.session_state:
    st.session_state.auto_login_done = False
if "order_log" not in st.session_state:
    st.session_state.order_log = []
if "ltp_cache" not in st.session_state:
    st.session_state.ltp_cache = {}
if "ltp_label" not in st.session_state:
    st.session_state.ltp_label = {}
if "selected_order" not in st.session_state:
    st.session_state.selected_order = "MARKET"
if "capital" not in st.session_state:
    st.session_state.capital = float(os.getenv("DEFAULT_CAPITAL", "10000"))
if "sl_pct_qty" not in st.session_state:
    st.session_state.sl_pct_qty = 1.0
if "sl_amount" not in st.session_state:
    st.session_state.sl_amount = 1000.0
if "sl_amount_limit" not in st.session_state:
    st.session_state.sl_amount_limit = 1000.0
if "quantity" not in st.session_state:
    st.session_state.quantity = 1
if "last_qty_source" not in st.session_state:
    st.session_state.last_qty_source = "auto"  # "auto" or "manual"

# ─── Helper Functions ─────────────────────────────────────────────────────────

def _session():
    s = requests.Session()
    s.headers.update({
        "authorization": f"enctoken {st.session_state.enctoken}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    return s

def _log(msg, kind="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.order_log.insert(0, {"ts": ts, "msg": msg, "kind": kind})

def check_token():
    if not st.session_state.enctoken:
        return False
    s = _session()
    resp = s.get(HIST_URL.format(instrument_id=86529, interval="minute"),
                 params={"user_id": st.session_state.user_id, "oi": "1",
                        "from": "2026-03-25", "to": "2026-03-25"})
    return resp.status_code == 200

def do_login(password, twofa):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
    r = s.post(LOGIN_URL, data={"user_id": st.session_state.user_id, "password": password})
    if r.status_code != 200:
        return False
    request_id = r.json()["data"]["request_id"]
    s.post(TWOFA_URL, data={"user_id": st.session_state.user_id,
                           "request_id": request_id, "twofa_value": twofa})
    cookies = requests.utils.dict_from_cookiejar(s.cookies)
    if "enctoken" in cookies:
        st.session_state.enctoken = cookies["enctoken"]
        return True
    return False

def fetch_ohlcv(ticker):
    from datetime import timedelta
    instrument_id = TOKEN_MAP.get(ticker)
    if not instrument_id:
        return None, f"No instrument ID for {ticker}"

    s = _session()
    today = datetime.now().date()
    from_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    try:
        # Fetch minute candles for today's OHLCV
        resp = s.get(HIST_URL.format(instrument_id=instrument_id, interval="minute"),
                     params={"user_id": st.session_state.user_id, "oi": "1",
                            "from": from_date, "to": to_date})
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"

        candles = resp.json().get("data", {}).get("candles", [])
        if not candles:
            return None, "No candles found in last 10 days"

        # Get last trading date from last candle
        last_date = candles[-1][0][:10]

        # Filter only last trading day's candles
        day_candles = [c for c in candles if c[0][:10] == last_date]

        if not day_candles:
            return None, "Could not isolate last trading day candles"

        open_price  = float(day_candles[0][1])   # first candle open
        high_price  = max(float(c[2]) for c in day_candles)
        low_price   = min(float(c[3]) for c in day_candles)
        close_price = float(day_candles[-1][4])   # last candle close
        volume      = sum(int(c[5]) for c in day_candles)

        # Fetch previous trading day for % change
        prev_candles = [c for c in candles if c[0][:10] < last_date]
        if prev_candles:
            prev_date = prev_candles[-1][0][:10]
            prev_day  = [c for c in prev_candles if c[0][:10] == prev_date]
            prev_close = float(prev_day[-1][4]) if prev_day else open_price
        else:
            prev_close = open_price  # fallback

        pct_change = ((close_price - prev_close) / prev_close) * 100

        return {
            "date"      : last_date,
            "open"      : open_price,
            "high"      : high_price,
            "low"       : low_price,
            "close"     : close_price,
            "volume"    : volume,
            "prev_close": prev_close,
            "pct_change": pct_change,
        }, None

    except Exception as e:
        return None, str(e)

def fetch_ltp(ticker):
    from datetime import timedelta
    instrument_id = TOKEN_MAP.get(ticker)
    if not instrument_id:
        return None, f"No instrument ID for {ticker}", None

    s = _session()
    today = datetime.now().date()
    from_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    try:
        resp = s.get(HIST_URL.format(instrument_id=instrument_id, interval="minute"),
                     params={"user_id": st.session_state.user_id, "oi": "1",
                            "from": from_date, "to": to_date})
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}", None

        candles = resp.json().get("data", {}).get("candles", [])
        if not candles:
            return None, "No candles found in last 10 days", None

        last_candle = candles[-1]
        ltp = float(last_candle[4])
        last_date = last_candle[0][:10]  # extract YYYY-MM-DD from timestamp
        label = "today" if last_date == to_date else last_date

        return ltp, None, label

    except Exception as e:
        return None, str(e), None

def place_market_order(tradingsymbol, transaction_type, quantity, exchange="NSE"):
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": tradingsymbol,
        "transaction_type": transaction_type, "quantity": quantity,
        "product": "MIS", "validity": "DAY", "variety": "regular",
        "order_type": "MARKET", "price": 0, "trigger_price": 0,
        "user_id": st.session_state.user_id,
    }
    resp = s.post(f"{ORDER_URL}/regular", data=payload)
    return resp.json()

def place_limit_order(tradingsymbol, transaction_type, quantity, price, exchange="NSE"):
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": tradingsymbol,
        "transaction_type": transaction_type, "quantity": quantity,
        "product": "MIS", "validity": "DAY", "variety": "regular",
        "order_type": "LIMIT", "price": price, "trigger_price": 0,
        "user_id": st.session_state.user_id,
    }
    resp = s.post(f"{ORDER_URL}/regular", data=payload)
    return resp.json()

def place_cover_market_order(tradingsymbol, transaction_type, quantity, trigger_price, exchange="NSE"):
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": tradingsymbol,
        "transaction_type": transaction_type, "quantity": quantity,
        "product": "MIS", "validity": "DAY", "variety": "co",
        "order_type": "MARKET", "price": 0, "trigger_price": trigger_price,
        "user_id": st.session_state.user_id,
    }
    resp = s.post(f"{ORDER_URL}/co", data=payload)
    return resp.json()

def place_cover_limit_order(tradingsymbol, transaction_type, quantity, price, trigger_price, exchange="NSE"):
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": tradingsymbol,
        "transaction_type": transaction_type, "quantity": quantity,
        "product": "MIS", "validity": "DAY", "variety": "co",
        "order_type": "LIMIT", "price": price, "trigger_price": trigger_price,
        "user_id": st.session_state.user_id,
    }
    resp = s.post(f"{ORDER_URL}/co", data=payload)
    return resp.json()

def compute_trigger(ltp, transaction_type, sl_pct):
    if transaction_type == "BUY":
        return round(ltp * (1 - sl_pct / 100), 2)
    else:
        return round(ltp * (1 + sl_pct / 100), 2)

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown('<div class="main-header">ZERODHA TRADING DASHBOARD</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">{len(SYMBOLS)} symbols loaded • MIS • Intraday</div>', unsafe_allow_html=True)

# ─── Authentication ───────────────────────────────────────────────────────────

# ─── Auto Login ───────────────────────────────────────────────────────────────
if not st.session_state.auto_login_done and not check_token():
    st.session_state.enctoken = ""
    if USER_ID and PASSWORD:
        with st.spinner("🔄 Token invalid — logging in automatically..."):
            s = requests.Session()
            s.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
            r = s.post(LOGIN_URL, data={"user_id": USER_ID, "password": PASSWORD})
            if r.status_code == 200:
                request_id = r.json()["data"]["request_id"]
                st.session_state["pending_request_id"] = request_id
                st.session_state["pending_user_id"]    = USER_ID
                st.session_state.auto_login_done       = True
                st.rerun()
            else:
                st.error(f"❌ Auto-login failed: {r.text[:200]}")

if st.session_state.get("pending_request_id"):
    st.markdown("### 🔐 Enter 2FA / TOTP")
    twofa_auto = st.text_input("2FA Code", key="auto_2fa",
                                placeholder="Enter your TOTP from authenticator app")
    if st.button("✅ Submit 2FA", key="submit_auto_2fa"):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        s.post(TWOFA_URL, data={
            "user_id":     st.session_state["pending_user_id"],
            "request_id":  st.session_state["pending_request_id"],
            "twofa_value": twofa_auto
        })
        cookies = requests.utils.dict_from_cookiejar(s.cookies)
        if "enctoken" in cookies:
            new_token = cookies["enctoken"]
            st.session_state.enctoken = new_token
            st.session_state.user_id  = st.session_state["pending_user_id"]
            # Save new token to .env
            env_path  = os.path.join(os.path.dirname(__file__), ".env")
            lines     = open(env_path).readlines() if os.path.exists(env_path) else []
            new_lines = [l for l in lines if not l.startswith("ENCTOKEN")]
            new_lines.append(f"ENCTOKEN={new_token}\n")
            open(env_path, "w").writelines(new_lines)
            del st.session_state["pending_request_id"]
            del st.session_state["pending_user_id"]
            _log("✅ Auto-login successful, token saved to .env", "success")
            st.success("✅ Logged in successfully!")
            st.rerun()
        else:
            st.error("❌ 2FA failed — check your TOTP code")
    st.stop()

with st.expander("🔐 Authentication", expanded=not bool(st.session_state.enctoken)):
    col1, col2 = st.columns(2)
    with col1:
        user_id = st.text_input("User ID", value=st.session_state.user_id, key="auth_user")
        st.session_state.user_id = user_id
        enctoken = st.text_input("Enctoken", value=st.session_state.enctoken, type="password", key="auth_enc")
        st.session_state.enctoken = enctoken
        if st.button("✓ Validate Token", use_container_width=True):
            if check_token():
                st.success("✅ Token valid")
                _log("Token validated", "success")
            else:
                st.error("❌ Token invalid")
    with col2:
        password = st.text_input("Password", type="password", key="auth_pwd")
        twofa = st.text_input("2FA/TOTP", key="auth_2fa")
        if st.button("🔑 Login", use_container_width=True):
            if do_login(password, twofa):
                st.success("✅ Login successful")
                _log("Login successful", "success")
                st.rerun()
            else:
                st.error("❌ Login failed")

st.markdown("<hr>", unsafe_allow_html=True)

# ─── Main Trading Interface ───────────────────────────────────────────────────

# Row 1: Symbol, Exchange, Transaction
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("<div class='section-title'>SYMBOL</div>", unsafe_allow_html=True)
    ticker = st.selectbox("symbol", SYMBOLS, index=SYMBOLS.index("RELIANCE") if "RELIANCE" in SYMBOLS else 0,
                         label_visibility="collapsed", key="symbol_select")
with col2:
    st.markdown("<div class='section-title'>EXCHANGE</div>", unsafe_allow_html=True)
    exchange = st.selectbox("exchange", ["NSE", "BSE"], label_visibility="collapsed", key="exchange_select")
with col3:
    st.markdown("<div class='section-title'>TRANSACTION</div>", unsafe_allow_html=True)
    txn_type = st.radio("txn", ["BUY", "SELL"], horizontal=True, label_visibility="collapsed", key="txn_type")

# Auto-fetch LTP on symbol change
if st.session_state.get("last_ticker") != ticker:
    st.session_state["last_ticker"] = ticker
    ltp, err, label = fetch_ltp(ticker)
    if ltp:
        st.session_state.ltp_cache[ticker] = ltp
        _log(f"LTP: ₹{ltp:,.2f} for {ticker}", "success")
    else:
        _log(f"Auto-fetch failed for {ticker}: {err}", "error")

ltp_now = st.session_state.ltp_cache.get(ticker)

# Row 2: LTP and Fetch button
col_ltp, col_fetch = st.columns([3, 1])
with col_ltp:
    if ltp_now:
        st.metric("LAST TRADED PRICE", f"₹{ltp_now:,.2f}")
    else:
        st.warning("Click Fetch LTP")
with col_fetch:
    st.markdown("<div style='margin-top: 1.8rem'></div>", unsafe_allow_html=True)
    if st.button("🔄 FETCH LTP", use_container_width=True, key="fetch_ltp"):
            ltp, err, label = fetch_ltp(ticker)
            if ltp:
                st.session_state.ltp_cache[ticker] = ltp
                st.success(f"LTP: ₹{ltp:,.2f}")
                _log(f"LTP fetched: ₹{ltp:,.2f}", "success")
            else:
                st.error(f"Failed: {err}")
# Stock Details
ohlcv, ohlcv_err = fetch_ohlcv(ticker)
if ohlcv:
    is_today = ohlcv["date"] == datetime.now().strftime("%Y-%m-%d")
    date_label = "TODAY" if is_today else f"LAST TRADED: {ohlcv['date']}"
    pct = ohlcv["pct_change"]
    pct_color = "#00e5a0" if pct >= 0 else "#ff4d6d"
    pct_arrow = "▲" if pct >= 0 else "▼"

    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">📊 STOCK DETAILS — {ticker} ({date_label})</div>
        <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.5rem; margin-top: 0.5rem;">
            <div class="metric-card">
                <div class="metric-label">OPEN</div>
                <div class="metric-value" style="font-size:1rem;">₹{ohlcv['open']:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">HIGH</div>
                <div class="metric-value" style="font-size:1rem; color:#00e5a0;">₹{ohlcv['high']:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">LOW</div>
                <div class="metric-value" style="font-size:1rem; color:#ff4d6d;">₹{ohlcv['low']:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">CLOSE / LTP</div>
                <div class="metric-value" style="font-size:1rem;">₹{ohlcv['close']:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">VOLUME</div>
                <div class="metric-value" style="font-size:1rem;">{"₹"+f"{ohlcv['volume']/1e7:.2f}Cr" if ohlcv['volume'] > 1e7 else f"{ohlcv['volume']:,}"}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">% CHANGE</div>
                <div class="metric-value" style="font-size:1rem; color:{pct_color};">{pct_arrow} {abs(pct):.2f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
elif ohlcv_err:
    st.warning(f"Could not load stock details: {ohlcv_err}")

# Row 3: Quantity Configuration
st.markdown("<div class='section-title'>QUANTITY</div>", unsafe_allow_html=True)

# ── Callbacks ──────────────────────────────────────────────────────────────
def on_capital_change():
    val = st.session_state.balance
    st.session_state.capital = val
    env_path  = os.path.join(os.path.dirname(__file__), ".env")
    lines     = open(env_path).readlines() if os.path.exists(env_path) else []
    new_lines = [l for l in lines if not l.startswith("DEFAULT_CAPITAL")]
    new_lines.append(f"DEFAULT_CAPITAL={val}\n")
    open(env_path, "w").writelines(new_lines)

def on_sl_pct_change():
    pct   = st.session_state.sl_pct_qty_input
    ltp   = st.session_state.ltp_cache.get(st.session_state.get("last_ticker"), 0)
    st.session_state.sl_pct_qty = pct
    if ltp > 0:
        sl_per_share = ltp * (pct / 100)
        new_qty      = max(1, int(st.session_state.sl_amount / sl_per_share))
        max_qty      = max(1, int((st.session_state.capital / ltp) * 5))
        st.session_state.quantity = min(new_qty, max_qty)

def on_sl_amount_change():
    amt  = st.session_state.sl_amount_input
    ltp  = st.session_state.ltp_cache.get(st.session_state.get("last_ticker"), 0)
    st.session_state.sl_amount = amt
    st.session_state.sl_amount_limit = amt  # update the limit too
    if ltp > 0:
        pct          = st.session_state.sl_pct_qty
        sl_per_share = ltp * (pct / 100)
        new_qty      = max(1, int(amt / sl_per_share))
        max_qty      = max(1, int((st.session_state.capital / ltp) * 5))
        st.session_state.quantity = min(new_qty, max_qty)

def on_qty_change():
    qty  = st.session_state.quantity_input
    ltp  = st.session_state.ltp_cache.get(st.session_state.get("last_ticker"), 0)
    st.session_state.quantity = qty
    if ltp > 0:
        pct          = st.session_state.sl_pct_qty
        sl_per_share = ltp * (pct / 100)
        st.session_state.sl_amount = round(qty * sl_per_share, 2)

# ── Inputs ─────────────────────────────────────────────────────────────────
col_c, col_sl, col_slamt, col_qty = st.columns(4)

with col_c:
    st.markdown("<div class='section-title'>CAPITAL (₹)</div>", unsafe_allow_html=True)
    st.number_input(
        "Capital", min_value=0.0,
        value=st.session_state.capital,
        step=1000.0, format="%.0f",
        label_visibility="collapsed",
        key="balance",
        on_change=on_capital_change
    )
    available_balance = st.session_state.capital

with col_sl:
    st.markdown("<div class='section-title'>% SL</div>", unsafe_allow_html=True)
    st.number_input(
        "SL %", min_value=0.01, max_value=100.0,
        value=st.session_state.sl_pct_qty,
        step=0.1, format="%.2f",
        label_visibility="collapsed",
        key="sl_pct_qty_input",
        on_change=on_sl_pct_change
    )
    sl_pct_qty = st.session_state.sl_pct_qty

with col_slamt:
    st.markdown("<div class='section-title'>MAX SL AMT (₹)</div>", unsafe_allow_html=True)
    st.number_input(
        "Max SL Amt", min_value=1.0,
        value=float(st.session_state.sl_amount),
        step=100.0, format="%.0f",
        label_visibility="collapsed",
        key="sl_amount_input",
        on_change=on_sl_amount_change
    )
    sl_amount = st.session_state.sl_amount

with col_qty:
    st.markdown("<div class='section-title'>QTY</div>", unsafe_allow_html=True)
    st.number_input(
        "Qty", min_value=1,
        value=int(st.session_state.quantity),
        step=1,
        label_visibility="collapsed",
        key="quantity_input",
        on_change=on_qty_change
    )
    quantity = st.session_state.quantity

# ── Info row ───────────────────────────────────────────────────────────────
if ltp_now and ltp_now > 0:
    sl_per_share   = ltp_now * (sl_pct_qty / 100)
    max_qty_by_cap = max(1, int((available_balance / ltp_now) * 5))
    # Always recalculate qty fresh from sl_amount and sl_pct — source of truth
    raw_qty        = max(1, int(sl_amount / sl_per_share)) if sl_per_share > 0 else 1
    capped         = raw_qty > max_qty_by_cap
    quantity       = min(raw_qty, max_qty_by_cap)  # this is the correct qty
    actual_sl      = quantity * sl_per_share        # max loss never exceeds sl_amount

    exceeds_sl = actual_sl > st.session_state.sl_amount_limit
    excess_amt = actual_sl - st.session_state.sl_amount_limit
    if capped:
        calc_text = (f"🧮 &nbsp; ₹{sl_amount:,.0f} ÷ ({sl_pct_qty}% × ₹{ltp_now:,.2f}) = "
                     f"<b>{raw_qty} shares</b> &nbsp;|&nbsp; "
                     f"⚠️ Capped to <b>{quantity}</b> by capital &nbsp;|&nbsp; "
                     f"Max loss: <b>₹{actual_sl:,.2f}</b>")
    elif exceeds_sl:
        calc_text = (f"🧮 &nbsp; ₹{sl_amount:,.0f} ÷ ({sl_pct_qty}% × ₹{ltp_now:,.2f}) = "
                     f"<b>{quantity} shares</b> &nbsp;|&nbsp; "
                     f"Max loss: <b>₹{actual_sl:,.2f}</b> &nbsp;"
                     f"⚠️ Exceeds max SL by <b>₹{excess_amt:,.2f}</b>")
    else:
        calc_text = (f"🧮 &nbsp; ₹{sl_amount:,.0f} ÷ ({sl_pct_qty}% × ₹{ltp_now:,.2f}) = "
                     f"<b>{quantity} shares</b> &nbsp;|&nbsp; "
                     f"Max loss: <b>₹{actual_sl:,.2f}</b>")

    bg = "linear-gradient(135deg, #ff4d6d 0%, #ff8c42 100%)" if exceeds_sl else "linear-gradient(135deg, #00e5a0 0%, #00b8ff 100%)"
    st.markdown(f"""
    <div style="
        background: {bg};
        border-radius: 8px;
        padding: 0.85rem 1.25rem;
        margin: 0.75rem 0;
        font-size: 1rem;
        font-weight: 600;
        color: #000000;
        letter-spacing: 0.01em;
    ">{calc_text}</div>
    """, unsafe_allow_html=True)

qty_mode = "SLAMT"

# Row 4: Order Type Buttons
st.markdown("<div class='section-title'>ORDER TYPE</div>", unsafe_allow_html=True)

order_col1, order_col2, order_col3, order_col4 = st.columns(4)

with order_col1:
    if st.button("📊 MARKET", use_container_width=True, key="btn_market"):
        st.session_state.selected_order = "MARKET"
        st.rerun()

with order_col2:
    if st.button("💰 LIMIT", use_container_width=True, key="btn_limit"):
        st.session_state.selected_order = "LIMIT"
        st.rerun()

with order_col3:
    if st.button("🛡️ COVER MARKET", use_container_width=True, key="btn_cover_market"):
        st.session_state.selected_order = "COVER_MARKET"
        st.rerun()

with order_col4:
    if st.button("⚡ COVER LIMIT", use_container_width=True, key="btn_cover_limit"):
        st.session_state.selected_order = "COVER_LIMIT"
        st.rerun()

# Highlight active button
st.markdown(f"<div style='text-align: center; margin-top: 0.5rem;'><small>Active: <b>{st.session_state.selected_order}</b></small></div>", unsafe_allow_html=True)

# Row 5: Order-specific inputs
limit_price = None
trigger_price = None
sl_pct = None

if st.session_state.selected_order in ["LIMIT", "COVER_LIMIT"]:
    col_price, _ = st.columns([1, 2])
    with col_price:
        st.markdown("<div class='section-title'>LIMIT PRICE (₹)</div>", unsafe_allow_html=True)
        default_limit = ltp_now if ltp_now and ltp_now > 0 else 100.0
        limit_price = st.number_input("limit", min_value=0.01, value=default_limit, step=0.5, format="%.2f", label_visibility="collapsed", key="limit_price")

if st.session_state.selected_order in ["COVER_MARKET", "COVER_LIMIT"]:
    col_sl1, col_sl2 = st.columns(2)
    with col_sl1:
        st.markdown("<div class='section-title'>STOP LOSS %</div>", unsafe_allow_html=True)
        sl_pct = st.number_input("slpct", min_value=0.1, max_value=10.0, value=1.0, step=0.1, format="%.1f", label_visibility="collapsed", key="sl_pct")
        if ltp_now:
            trigger_price = compute_trigger(ltp_now, txn_type, sl_pct)
            st.caption(f"Trigger: ₹{trigger_price:,.2f}")
    with col_sl2:
        st.markdown("<div class='section-title'>OVERRIDE TRIGGER (₹)</div>", unsafe_allow_html=True)
        manual_trigger = st.number_input("manual", min_value=0.0, value=0.0, step=0.5, format="%.2f", label_visibility="collapsed", key="manual_trigger")
        if manual_trigger > 0:
            trigger_price = manual_trigger

    # Recompute qty based on sl_pct when SLAMT mode is active
    if qty_mode == "SLAMT" and ltp_now and ltp_now > 0:
        sl_per_share     = ltp_now * (sl_pct / 100)        # use actual sl% not hardcoded 1%
        qty_by_sl        = max(1, int(sl_amount / sl_per_share))
        max_qty_by_balance = max(1, int((available_balance / ltp_now) * 5))

        if qty_by_sl > max_qty_by_balance:
            quantity = max_qty_by_balance
            sl_info = (f"SL ₹{sl_amount:,.0f} ÷ ({sl_pct}% × ₹{ltp_now:,.2f}) = {qty_by_sl} shares "
                      f"| ⚠️ Capped to **{quantity}** by balance")
        else:
            quantity = qty_by_sl
            sl_info = (f"SL ₹{sl_amount:,.0f} ÷ ({sl_pct}% × ₹{ltp_now:,.2f}) = **{quantity} shares** "
                      f"| Max loss: ₹{quantity * sl_per_share:,.2f}")

        st.markdown(f'<div class="info-box">🧮 {sl_info}</div>', unsafe_allow_html=True)

        # Show updated qty
        st.markdown(f"""
        <div class="metric-card" style="margin-top:0.5rem;">
            <div class="metric-label">CALCULATED QTY (from SL%)</div>
            <div class="metric-value">🔢 {quantity} shares</div>
        </div>
        """, unsafe_allow_html=True)

# Row 6: Order Preview & Metrics
if ltp_now:
    # Preview
    preview_text = f"{txn_type} • {quantity} × {ticker}"
    if st.session_state.selected_order in ["LIMIT", "COVER_LIMIT"] and limit_price:
        preview_text += f" @ ₹{limit_price:,.2f}"
    else:
        preview_text += f" @ MARKET"
    if st.session_state.selected_order in ["COVER_MARKET", "COVER_LIMIT"] and trigger_price:
        preview_text += f" • SL: ₹{trigger_price:,.2f}"
        if sl_pct:
            preview_text += f" ({sl_pct}%)"

    st.markdown(f'<div class="info-box">📋 {preview_text} • MIS • Intraday</div>', unsafe_allow_html=True)

    # Metrics for cover orders
    if st.session_state.selected_order in ["COVER_MARKET", "COVER_LIMIT"] and trigger_price and ltp_now:
        sl_amt = abs(ltp_now - trigger_price)
        total_sl = sl_amt * quantity

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">LTP</div>
                <div class="metric-value">₹{ltp_now:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">SL TRIGGER</div>
                <div class="metric-value red">₹{trigger_price:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">MAX LOSS</div>
                <div class="metric-value red">₹{total_sl:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.warning("⚠️ Click 'FETCH LTP' to continue")

# Row 7: Action Buttons
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    place_order = st.button("▶ PLACE ORDER", use_container_width=True, type="primary", key="place_order")
with col_btn2:
    clear_log = st.button("🗑️ CLEAR LOG", use_container_width=True, key="clear_log")

if clear_log:
    st.session_state.order_log = []

# Place Order Logic
if place_order:
    if not st.session_state.enctoken:
        st.error("❌ Please authenticate first")
    elif not ltp_now:
        st.error("❌ Please fetch LTP first")
    elif st.session_state.selected_order in ["LIMIT", "COVER_LIMIT"] and (not limit_price or limit_price <= 0):
        st.error("❌ Please enter valid limit price")
    elif st.session_state.selected_order in ["COVER_MARKET", "COVER_LIMIT"] and (not trigger_price or trigger_price <= 0):
        st.error("❌ Please set valid trigger price")
    else:
        with st.spinner("Placing order..."):
            try:
                if st.session_state.selected_order == "MARKET":
                    result = place_market_order(ticker, txn_type, quantity, exchange)
                    desc = f"MARKET {txn_type}"
                elif st.session_state.selected_order == "LIMIT":
                    result = place_limit_order(ticker, txn_type, quantity, limit_price, exchange)
                    desc = f"LIMIT {txn_type} @ ₹{limit_price:,.2f}"
                elif st.session_state.selected_order == "COVER_MARKET":
                    result = place_cover_market_order(ticker, txn_type, quantity, trigger_price, exchange)
                    desc = f"COVER MARKET {txn_type} (SL: ₹{trigger_price:,.2f})"
                elif st.session_state.selected_order == "COVER_LIMIT":
                    result = place_cover_limit_order(ticker, txn_type, quantity, limit_price, trigger_price, exchange)
                    desc = f"COVER LIMIT {txn_type} @ ₹{limit_price:,.2f} (SL: ₹{trigger_price:,.2f})"
                else:
                    result = None
                    desc = ""

                if result and result.get("status") == "success":
                    oid = result.get("data", {}).get("order_id", "N/A")
                    st.success(f"✅ Order placed! ID: {oid}")
                    _log(f"✅ {desc} | {quantity}×{ticker} | ID: {oid}", "success")
                elif result:
                    msg = result.get("message", str(result))
                    st.error(f"❌ Order failed: {msg}")
                    _log(f"❌ {desc} failed: {msg}", "error")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                _log(f"❌ Error: {str(e)}", "error")

st.markdown("<hr>", unsafe_allow_html=True)

# ─── Activity Log ────────────────────────────────────────────────────────────

st.markdown("<div class='section-title'>📋 ACTIVITY LOG</div>", unsafe_allow_html=True)

if st.session_state.order_log:
    log_html = '<div class="log-container">'
    for entry in st.session_state.order_log[:20]:
        cls = "log-success" if entry["kind"] == "success" else "log-error" if entry["kind"] == "error" else "log-entry"
        log_html += f'<div class="{cls}">[{entry["ts"]}] {entry["msg"]}</div>'
    log_html += '</div>'
    st.markdown(log_html, unsafe_allow_html=True)
else:
    st.caption("No activity yet")