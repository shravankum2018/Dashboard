"""
scalp_page.py
─────────────────────────────────────────────────────────────────────────────
Scalping module for Zerodha Trading Dashboard.
Import and call render_scalp_page() from your main app's multipage router.

Logic:
  • Market order entry (immediate fill at LTP)
  • Stop-Loss  : entry × (1 - sl_pct/100)   for BUY
                 entry × (1 + sl_pct/100)   for SELL
  • Target     : entry × (1 + tgt_ratio × sl_pct/100)  for BUY
                 entry × (1 - tgt_ratio × sl_pct/100)  for SELL
  • tgt_ratio  : default 1.5  (R:R = 1:1.5)
  • After entry the module displays SL / Target levels and
    lets the user place the bracket SL-limit leg manually
    (Zerodha's bracket order / SL-M leg).
─────────────────────────────────────────────────────────────────────────────
"""

import streamlit as st
import requests
import os
import pandas as pd
from datetime import datetime, timedelta

# ─── Re-use helpers from the parent app ──────────────────────────────────────
# These are set by the parent app before calling render_scalp_page().
# Required session-state keys: enctoken, user_id, ltp_cache, order_log
# Required globals injected by parent: TOKEN_MAP, SYMBOLS, BASE_URL, HIST_URL

BASE_URL  = "https://kite.zerodha.com"
ORDER_URL = f"{BASE_URL}/oms/orders"
HIST_URL  = f"{BASE_URL}/oms/instruments/historical/{{instrument_id}}/{{interval}}"


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _session():
    s = requests.Session()
    s.headers.update({
        "authorization": f"enctoken {st.session_state.enctoken}",
        "Content-Type":  "application/x-www-form-urlencoded",
    })
    return s


def _log(msg: str, kind: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.order_log.insert(0, {"ts": ts, "msg": msg, "kind": kind})


def _fetch_ltp(ticker: str, token_map: dict) -> tuple[float | None, str | None]:
    """Returns (ltp, error_string)."""
    instrument_id = token_map.get(ticker)
    if not instrument_id:
        return None, f"No token for {ticker}"

    s         = _session()
    today     = datetime.now().date()
    from_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    to_date   = today.strftime("%Y-%m-%d")

    try:
        resp = s.get(
            HIST_URL.format(instrument_id=instrument_id, interval="minute"),
            params={"user_id": st.session_state.user_id, "oi": "1",
                    "from": from_date, "to": to_date},
        )
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        candles = resp.json().get("data", {}).get("candles", [])
        if not candles:
            return None, "No candles"
        return float(candles[-1][4]), None
    except Exception as e:
        return None, str(e)


def _place_market_order(symbol, txn, qty, exchange):
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": symbol,
        "transaction_type": txn, "quantity": qty,
        "product": "MIS", "validity": "DAY", "variety": "regular",
        "order_type": "MARKET", "price": 0, "trigger_price": 0,
        "user_id": st.session_state.user_id,
    }
    return s.post(f"{ORDER_URL}/regular", data=payload).json()


def _place_sl_order(symbol, txn, qty, trigger, price, exchange):
    """SL-M order for the stop-loss leg after entry."""
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": symbol,
        "transaction_type": txn, "quantity": qty,
        "product": "MIS", "validity": "DAY", "variety": "regular",
        "order_type": "SL-M", "price": price, "trigger_price": trigger,
        "user_id": st.session_state.user_id,
    }
    return s.post(f"{ORDER_URL}/regular", data=payload).json()


def _place_limit_order(symbol, txn, qty, price, exchange):
    """Limit order for the target leg after entry."""
    s = _session()
    payload = {
        "exchange": exchange, "tradingsymbol": symbol,
        "transaction_type": txn, "quantity": qty,
        "product": "MIS", "validity": "DAY", "variety": "regular",
        "order_type": "LIMIT", "price": price, "trigger_price": 0,
        "user_id": st.session_state.user_id,
    }
    return s.post(f"{ORDER_URL}/regular", data=payload).json()


def _calc_levels(entry: float, txn: str, sl_pct: float, rr: float):
    """Returns (sl_price, target_price, sl_pts, tgt_pts, actual_rr)."""
    sl_pts  = round(entry * sl_pct / 100, 2)
    tgt_pts = round(sl_pts * rr, 2)

    if txn == "BUY":
        sl_price  = round(entry - sl_pts, 2)
        tgt_price = round(entry + tgt_pts, 2)
    else:
        sl_price  = round(entry + sl_pts, 2)
        tgt_price = round(entry - tgt_pts, 2)

    return sl_price, tgt_price, sl_pts, tgt_pts, rr


# ─── CSS (dark theme matching parent) ────────────────────────────────────────

_SCALP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap');

.scalp-header {
    font-family: 'Space Mono', monospace;
    font-size: 1.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #ff6b35 0%, #f7c59f 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
    margin-bottom: 0.25rem;
}

.scalp-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem;
    color: #4a5060;
    margin-bottom: 1rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.scalp-card {
    background: #111318;
    border: 1px solid #1e2128;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.75rem;
    font-family: 'DM Sans', sans-serif;
}

.scalp-card-title {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #4a5060;
    margin-bottom: 0.75rem;
}

.level-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 0.6rem;
}

.level-box {
    background: #0a0c10;
    border: 1px solid #1e2128;
    border-radius: 8px;
    padding: 0.7rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}

.level-box.entry { border-top: 2px solid #00b8ff; }
.level-box.target { border-top: 2px solid #00e5a0; }
.level-box.sl { border-top: 2px solid #ff4d6d; }
.level-box.rr { border-top: 2px solid #f7c59f; }

.level-label {
    font-size: 0.6rem;
    color: #4a5060;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.3rem;
}

.level-val {
    font-family: 'Space Mono', monospace;
    font-size: 1.05rem;
    font-weight: 700;
}

.level-val.entry-color  { color: #00b8ff; }
.level-val.target-color { color: #00e5a0; }
.level-val.sl-color     { color: #ff4d6d; }
.level-val.rr-color     { color: #f7c59f; }

.level-sub {
    font-size: 0.65rem;
    color: #4a5060;
    margin-top: 0.2rem;
}

.rr-bar-outer {
    background: #0a0c10;
    border: 1px solid #1e2128;
    border-radius: 6px;
    height: 10px;
    width: 100%;
    margin-top: 0.5rem;
    overflow: hidden;
}

.rr-bar-inner {
    height: 100%;
    background: linear-gradient(90deg, #ff4d6d 0%, #00e5a0 100%);
    border-radius: 6px;
}

.tip-box {
    background: rgba(255, 107, 53, 0.06);
    border-left: 3px solid #ff6b35;
    border-radius: 6px;
    padding: 0.7rem 1rem;
    font-size: 0.8rem;
    color: #8890a0;
    font-family: 'DM Sans', sans-serif;
    margin-bottom: 0.75rem;
}

.trade-log {
    background: #0a0c10;
    border: 1px solid #1e2128;
    border-radius: 8px;
    padding: 0.75rem;
    max-height: 160px;
    overflow-y: auto;
    font-size: 0.72rem;
    font-family: 'Space Mono', monospace;
}

.tlog-entry { color: #8890a0; padding: 0.2rem 0; border-bottom: 1px solid #1e2128; }
.tlog-ok    { color: #00e5a0; }
.tlog-err   { color: #ff4d6d; }

.btn-fire {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
}

.stat-pill {
    display: inline-block;
    background: #1e2128;
    border-radius: 20px;
    padding: 0.25rem 0.75rem;
    font-size: 0.7rem;
    color: #8890a0;
    margin-right: 0.5rem;
    font-family: 'DM Sans', sans-serif;
}

.stat-pill b { color: #e8eaf0; }
</style>
"""


# ─── Main render function ─────────────────────────────────────────────────────

def render_scalp_page(symbols: list[str], token_map: dict):
    """
    Call this from your multipage Streamlit app.
    `symbols`   – sorted list of symbol strings (from main app)
    `token_map` – dict {symbol: instrument_token} (from main app)
    """

    st.markdown(_SCALP_CSS, unsafe_allow_html=True)

    # ── Init session state keys ───────────────────────────────────────────────
    for key, default in [
        ("scalp_ltp",          None),
        ("scalp_entry",        None),
        ("scalp_order_id",     None),
        ("scalp_active",       False),   # True after entry fired
        ("scalp_sl_placed",    False),
        ("scalp_tgt_placed",   False),
        ("scalp_trade_log",    []),
        ("scalp_wins",         0),
        ("scalp_losses",       0),
        ("scalp_pnl",          0.0),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if "order_log" not in st.session_state:
        st.session_state.order_log = []

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown('<div class="scalp-header">⚡ SCALP MODE</div>', unsafe_allow_html=True)
    st.markdown('<div class="scalp-sub">Market entry · 1% SL · Configurable R:R · MIS intraday</div>', unsafe_allow_html=True)

    # ── Tips banner ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="tip-box">
    💡 <b>Scalping tip:</b> A flat 1:1 R:R needs >55% win rate to profit after Zerodha brokerage + STT.
    Try <b>1.5× or 2× R:R</b> — you can win only 40% of trades and still be profitable.
    Always place your SL leg <b>immediately</b> after entry fills.
    </div>
    """, unsafe_allow_html=True)

    # ── Session stats ─────────────────────────────────────────────────────────
    total_trades = st.session_state.scalp_wins + st.session_state.scalp_losses
    win_rate     = (st.session_state.scalp_wins / total_trades * 100) if total_trades else 0
    pnl_color    = "#00e5a0" if st.session_state.scalp_pnl >= 0 else "#ff4d6d"

    st.markdown(f"""
    <span class="stat-pill">Trades: <b>{total_trades}</b></span>
    <span class="stat-pill">Wins: <b style="color:#00e5a0">{st.session_state.scalp_wins}</b></span>
    <span class="stat-pill">Losses: <b style="color:#ff4d6d">{st.session_state.scalp_losses}</b></span>
    <span class="stat-pill">Win Rate: <b>{win_rate:.0f}%</b></span>
    <span class="stat-pill">Session P&L: <b style="color:{pnl_color}">₹{st.session_state.scalp_pnl:,.2f}</b></span>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── STEP 1: Setup ─────────────────────────────────────────────────────────
    st.markdown('<div class="scalp-card"><div class="scalp-card-title">⚙️ Step 1 — Setup</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        scalp_ticker = st.selectbox(
            "Symbol", symbols,
            index=symbols.index("RELIANCE") if "RELIANCE" in symbols else 0,
            key="scalp_symbol",
        )
    with c2:
        scalp_exchange = st.selectbox("Exchange", ["NSE", "BSE"], key="scalp_exchange")
    with c3:
        scalp_txn = st.radio("Side", ["BUY", "SELL"], horizontal=True, key="scalp_txn")
    with c4:
        scalp_qty = st.number_input("Qty", min_value=1, value=1, step=1, key="scalp_qty")

    c5, c6, c7 = st.columns(3)
    with c5:
        sl_pct = st.number_input("SL %", min_value=0.1, max_value=5.0,
                                  value=1.0, step=0.1, format="%.1f", key="scalp_sl_pct")
    with c6:
        rr = st.number_input("R:R (target multiplier)", min_value=0.5, max_value=10.0,
                              value=1.5, step=0.1, format="%.1f", key="scalp_rr",
                              help="1.5 means target = 1.5× your SL distance")
    with c7:
        auto_sl  = st.toggle("Auto-place SL leg",  value=True,  key="scalp_auto_sl")
        auto_tgt = st.toggle("Auto-place Tgt leg", value=False, key="scalp_auto_tgt",
                              help="Places a limit order for target simultaneously")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Fetch LTP ─────────────────────────────────────────────────────────────
    col_ltp, col_fetch = st.columns([3, 1])
    with col_ltp:
        ltp_display = st.session_state.scalp_ltp
        if ltp_display:
            st.metric("LTP", f"₹{ltp_display:,.2f}")
        else:
            st.info("Fetch LTP to preview levels")

    with col_fetch:
        st.markdown("<div style='margin-top:1.75rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 FETCH LTP", key="scalp_fetch_ltp", use_container_width=True):
            ltp, err = _fetch_ltp(scalp_ticker, token_map)
            if ltp:
                st.session_state.scalp_ltp = ltp
                st.session_state.ltp_cache[scalp_ticker] = ltp
                st.success(f"₹{ltp:,.2f}")
            else:
                st.error(f"Failed: {err}")

    # ── Level Preview ─────────────────────────────────────────────────────────
    ltp_now = st.session_state.scalp_ltp

    if ltp_now:
        sl_px, tgt_px, sl_pts, tgt_pts, _ = _calc_levels(ltp_now, scalp_txn, sl_pct, rr)

        max_loss  = round(sl_pts  * scalp_qty, 2)
        max_gain  = round(tgt_pts * scalp_qty, 2)
        rr_bar_w  = min(int((rr / 4) * 100), 100)    # visual bar up to 4R

        st.markdown(f"""
        <div class="scalp-card">
            <div class="scalp-card-title">📐 Level Preview (based on LTP)</div>
            <div class="level-grid">
                <div class="level-box entry">
                    <div class="level-label">ENTRY (Market)</div>
                    <div class="level-val entry-color">~₹{ltp_now:,.2f}</div>
                    <div class="level-sub">fills at market</div>
                </div>
                <div class="level-box target">
                    <div class="level-label">TARGET (+{sl_pct*rr:.2f}%)</div>
                    <div class="level-val target-color">₹{tgt_px:,.2f}</div>
                    <div class="level-sub">+₹{tgt_pts:,.2f}/share · ₹{max_gain:,.2f} total</div>
                </div>
                <div class="level-box sl">
                    <div class="level-label">STOP LOSS (-{sl_pct:.1f}%)</div>
                    <div class="level-val sl-color">₹{sl_px:,.2f}</div>
                    <div class="level-sub">-₹{sl_pts:,.2f}/share · ₹{max_loss:,.2f} total</div>
                </div>
                <div class="level-box rr">
                    <div class="level-label">R:R RATIO</div>
                    <div class="level-val rr-color">1 : {rr:.1f}</div>
                    <div class="level-sub">min win rate: {100/(1+rr):.0f}%</div>
                </div>
            </div>
            <div class="rr-bar-outer">
                <div class="rr-bar-inner" style="width:{rr_bar_w}%"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── STEP 2: Fire Entry ────────────────────────────────────────────────────
    st.markdown('<div class="scalp-card"><div class="scalp-card-title">🚀 Step 2 — Fire Entry</div>', unsafe_allow_html=True)

    col_b1, col_b2, col_b3 = st.columns(3)

    with col_b1:
        fire = st.button(
            f"▶ {'BUY' if scalp_txn == 'BUY' else 'SELL'} {scalp_qty} × {scalp_ticker}",
            use_container_width=True,
            type="primary",
            key="scalp_fire",
            disabled=not bool(st.session_state.enctoken and ltp_now),
        )

    with col_b2:
        if st.session_state.scalp_active:
            if st.button("📌 Place SL Leg", use_container_width=True, key="scalp_place_sl",
                          disabled=st.session_state.scalp_sl_placed):
                entry = st.session_state.scalp_entry
                if entry:
                    sl_px2, _, sl_pts2, _, _ = _calc_levels(entry, scalp_txn, sl_pct, rr)
                    exit_txn = "SELL" if scalp_txn == "BUY" else "BUY"
                    result = _place_sl_order(scalp_ticker, exit_txn, scalp_qty,
                                             trigger=sl_px2,
                                             price=round(sl_px2 * 0.998, 2),
                                             exchange=scalp_exchange)
                    if result.get("status") == "success":
                        st.session_state.scalp_sl_placed = True
                        oid = result["data"].get("order_id", "")
                        st.success(f"SL placed ✓ ID: {oid}")
                        _log(f"✅ SL-M placed @ ₹{sl_px2} | {oid}", "success")
                    else:
                        st.error(result.get("message", "SL failed"))

    with col_b3:
        if st.session_state.scalp_active:
            if st.button("🎯 Place Target Leg", use_container_width=True, key="scalp_place_tgt",
                          disabled=st.session_state.scalp_tgt_placed):
                entry = st.session_state.scalp_entry
                if entry:
                    _, tgt_px2, _, _, _ = _calc_levels(entry, scalp_txn, sl_pct, rr)
                    exit_txn = "SELL" if scalp_txn == "BUY" else "BUY"
                    result = _place_limit_order(scalp_ticker, exit_txn, scalp_qty,
                                                price=tgt_px2, exchange=scalp_exchange)
                    if result.get("status") == "success":
                        st.session_state.scalp_tgt_placed = True
                        oid = result["data"].get("order_id", "")
                        st.success(f"Target placed ✓ ID: {oid}")
                        _log(f"✅ Limit target @ ₹{tgt_px2} | {oid}", "success")
                    else:
                        st.error(result.get("message", "Target failed"))

    # ── Active trade status ───────────────────────────────────────────────────
    if st.session_state.scalp_active and st.session_state.scalp_entry:
        entry = st.session_state.scalp_entry
        sl_px3, tgt_px3, _, _, _ = _calc_levels(entry, scalp_txn, sl_pct, rr)
        sl_stat  = "✅ Placed" if st.session_state.scalp_sl_placed  else "⚠️ Not placed"
        tgt_stat = "✅ Placed" if st.session_state.scalp_tgt_placed else "⚠️ Not placed"

        st.markdown(f"""
        <div style="background:#0a3a22;border:1px solid #00e5a0;border-radius:8px;
                    padding:0.75rem 1.2rem;margin:0.5rem 0;font-size:0.85rem;color:#e8eaf0;">
        🟢 <b>ACTIVE TRADE</b> &nbsp;|&nbsp;
        Entry: <b style="color:#00b8ff">₹{entry:,.2f}</b> &nbsp;|&nbsp;
        SL: <b style="color:#ff4d6d">₹{sl_px3:,.2f}</b> ({sl_stat}) &nbsp;|&nbsp;
        Target: <b style="color:#00e5a0">₹{tgt_px3:,.2f}</b> ({tgt_stat})
        </div>
        """, unsafe_allow_html=True)

        c_win, c_loss, c_reset = st.columns(3)
        with c_win:
            if st.button("✅ Mark WIN", use_container_width=True, key="scalp_win"):
                _, tgt_px4, _, tgt_pts4, _ = _calc_levels(entry, scalp_txn, sl_pct, rr)
                pnl = tgt_pts4 * scalp_qty
                st.session_state.scalp_wins  += 1
                st.session_state.scalp_pnl   += pnl
                st.session_state.scalp_trade_log.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": scalp_ticker, "side": scalp_txn, "qty": scalp_qty,
                    "entry": entry, "exit": tgt_px4, "pnl": pnl, "result": "WIN"
                })
                _log(f"✅ WIN | {scalp_ticker} | +₹{pnl:,.2f}", "success")
                _reset_trade()
                st.rerun()

        with c_loss:
            if st.button("❌ Mark LOSS", use_container_width=True, key="scalp_loss"):
                sl_px4, _, sl_pts4, _, _ = _calc_levels(entry, scalp_txn, sl_pct, rr)
                pnl = -sl_pts4 * scalp_qty
                st.session_state.scalp_losses += 1
                st.session_state.scalp_pnl    += pnl
                st.session_state.scalp_trade_log.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": scalp_ticker, "side": scalp_txn, "qty": scalp_qty,
                    "entry": entry, "exit": sl_px4, "pnl": pnl, "result": "LOSS"
                })
                _log(f"❌ LOSS | {scalp_ticker} | -₹{abs(pnl):,.2f}", "error")
                _reset_trade()
                st.rerun()

        with c_reset:
            if st.button("🔄 Reset Trade", use_container_width=True, key="scalp_reset"):
                _reset_trade()
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Fire logic ────────────────────────────────────────────────────────────
    if fire:
        if not st.session_state.enctoken:
            st.error("Not authenticated")
        elif not ltp_now:
            st.error("Fetch LTP first")
        else:
            with st.spinner("Placing entry order..."):
                result = _place_market_order(scalp_ticker, scalp_txn, scalp_qty, scalp_exchange)
            if result.get("status") == "success":
                oid   = result["data"].get("order_id", "")
                entry = ltp_now  # approximate; real fill comes from order book

                st.session_state.scalp_entry     = entry
                st.session_state.scalp_order_id  = oid
                st.session_state.scalp_active     = True
                st.session_state.scalp_sl_placed  = False
                st.session_state.scalp_tgt_placed = False

                sl_px_f, tgt_px_f, _, _, _ = _calc_levels(entry, scalp_txn, sl_pct, rr)
                _log(f"✅ ENTRY {scalp_txn} {scalp_qty}×{scalp_ticker} @ ~₹{entry} | ID:{oid}", "success")
                st.success(f"✅ Entry placed! ID: {oid}")

                # Auto-place legs if toggled
                if auto_sl:
                    exit_txn = "SELL" if scalp_txn == "BUY" else "BUY"
                    sl_r = _place_sl_order(scalp_ticker, exit_txn, scalp_qty,
                                           trigger=sl_px_f,
                                           price=round(sl_px_f * 0.998, 2),
                                           exchange=scalp_exchange)
                    if sl_r.get("status") == "success":
                        st.session_state.scalp_sl_placed = True
                        _log(f"✅ Auto SL-M @ ₹{sl_px_f} | {sl_r['data'].get('order_id','')}", "success")

                if auto_tgt:
                    exit_txn = "SELL" if scalp_txn == "BUY" else "BUY"
                    tgt_r = _place_limit_order(scalp_ticker, exit_txn, scalp_qty,
                                               price=tgt_px_f, exchange=scalp_exchange)
                    if tgt_r.get("status") == "success":
                        st.session_state.scalp_tgt_placed = True
                        _log(f"✅ Auto Target @ ₹{tgt_px_f} | {tgt_r['data'].get('order_id','')}", "success")

                st.rerun()
            else:
                msg = result.get("message", str(result))
                st.error(f"❌ Entry failed: {msg}")
                _log(f"❌ Entry failed: {msg}", "error")

    # ── Trade History ─────────────────────────────────────────────────────────
    if st.session_state.scalp_trade_log:
        st.markdown('<div class="scalp-card-title" style="margin-top:1rem">📜 TRADE HISTORY (this session)</div>', unsafe_allow_html=True)
        df = pd.DataFrame(st.session_state.scalp_trade_log)
        df["pnl"] = df["pnl"].map(lambda x: f"₹{x:+,.2f}")
        df.columns = [c.upper() for c in df.columns]
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Activity Log ──────────────────────────────────────────────────────────
    st.markdown('<div class="scalp-card-title" style="margin-top:1rem">📋 LOG</div>', unsafe_allow_html=True)
    if st.session_state.order_log:
        log_html = '<div class="trade-log">'
        for e in st.session_state.order_log[:15]:
            cls = "tlog-ok" if e["kind"] == "success" else "tlog-err" if e["kind"] == "error" else "tlog-entry"
            log_html += f'<div class="{cls}">[{e["ts"]}] {e["msg"]}</div>'
        log_html += '</div>'
        st.markdown(log_html, unsafe_allow_html=True)
    else:
        st.caption("No activity yet")

    col_clr, _ = st.columns([1, 4])
    with col_clr:
        if st.button("🗑️ Clear Log", key="scalp_clear_log"):
            st.session_state.order_log = []
            st.rerun()


def _reset_trade():
    st.session_state.scalp_active     = False
    st.session_state.scalp_entry      = None
    st.session_state.scalp_order_id   = None
    st.session_state.scalp_sl_placed  = False
    st.session_state.scalp_tgt_placed = False