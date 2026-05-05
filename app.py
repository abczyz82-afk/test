import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import time
import random

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="VN30F Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS  – Bloomberg-dark terminal
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    background-color: #0a0e1a;
    color: #e2e8f0;
}
.stApp { background: #0a0e1a; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f1526;
    border-right: 1px solid #1e2d4a;
}
section[data-testid="stSidebar"] * { color: #c9d5e8 !important; }

/* Cards */
.signal-card {
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 1px;
    text-align: center;
}
.uptrend  { background: linear-gradient(135deg,#0d2b1e,#0f3b26); border:1.5px solid #00e676; color:#00e676; }
.downtrend{ background: linear-gradient(135deg,#2b0d0d,#3b0f0f); border:1.5px solid #ff5252; color:#ff5252; }
.sideway  { background: linear-gradient(135deg,#1a1a2b,#1e1e3b); border:1.5px solid #ffd600; color:#ffd600; }

/* Metric boxes */
.metric-box {
    background: #111827;
    border: 1px solid #1e2d4a;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.metric-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.green { color: #00e676; }
.red   { color: #ff5252; }
.yellow{ color: #ffd600; }
.white { color: #f1f5f9; }
.blue  { color: #38bdf8; }

/* Section headers */
.section-header {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #475569;
    border-bottom: 1px solid #1e2d4a;
    padding-bottom: 6px;
    margin-bottom: 12px;
}

/* Trade row */
.trade-row {
    background: #111827;
    border: 1px solid #1e2d4a;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    display: flex;
    justify-content: space-between;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg,#1e40af,#1d4ed8);
    color: white;
    border: none;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    letter-spacing: 0.5px;
}
.stButton > button:hover { background: linear-gradient(135deg,#1d4ed8,#2563eb); }

/* Tabs */
.stTabs [data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 1px;
    color: #64748b;
}
.stTabs [aria-selected="true"] { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }

/* Selectbox */
.stSelectbox > div > div { background: #111827; border-color: #1e2d4a; color: #e2e8f0; }

/* Number input */
.stNumberInput > div > div > input { background: #111827; border-color: #1e2d4a; color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if "seed" not in st.session_state:
    st.session_state.seed = random.randint(0, 9999)


# ─────────────────────────────────────────────
# DATA GENERATION – Simulated VN30F OHLCV
# ─────────────────────────────────────────────
def generate_ohlcv(tf_minutes: int, n_bars: int = 200, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed + tf_minutes)
    now = datetime.now().replace(second=0, microsecond=0)
    now -= timedelta(minutes=now.minute % tf_minutes)
    times = [now - timedelta(minutes=tf_minutes * i) for i in range(n_bars)][::-1]

    # Simulate realistic price walk with trending & sideway phases
    base = 1280.0
    prices = [base]
    trend_strength = 0.0
    volatility = 0.4

    for i in range(1, n_bars):
        # Phase rotation
        phase = (i // 30) % 3  # 0=up, 1=side, 2=down
        if phase == 0:
            drift = 0.15
        elif phase == 2:
            drift = -0.12
        else:
            drift = 0.0
        volatility = 0.35 if phase == 1 else 0.55
        change = drift + np.random.normal(0, volatility)
        prices.append(max(prices[-1] + change, 100))

    df = pd.DataFrame({"time": times})
    df["close"] = prices

    # Build OHLC from close
    noise = [abs(np.random.normal(0, 0.3)) + 0.1 for _ in range(n_bars)]
    df["open"]  = df["close"].shift(1).fillna(df["close"].iloc[0])
    df["high"]  = df[["open","close"]].max(axis=1) + pd.Series(noise)
    df["low"]   = df[["open","close"]].min(axis=1) - pd.Series(noise)
    df["volume"]= np.random.randint(200, 2500, n_bars)
    return df.set_index("time")


# ─────────────────────────────────────────────
# TECHNICAL INDICATORS
# ─────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    n = len(c)

    # --- EMAs ---
    def ema(arr, period):
        result = np.full(len(arr), np.nan)
        k = 2 / (period + 1)
        result[period - 1] = arr[:period].mean()
        for i in range(period, len(arr)):
            result[i] = arr[i] * k + result[i-1] * (1 - k)
        return result

    df["ema9"]  = ema(c, 9)
    df["ema21"] = ema(c, 21)
    df["ema50"] = ema(c, 50)

    # --- Bollinger Bands (20, 2) ---
    roll_mean = pd.Series(c).rolling(20).mean().values
    roll_std  = pd.Series(c).rolling(20).std().values
    df["bb_mid"]   = roll_mean
    df["bb_upper"] = roll_mean + 2 * roll_std
    df["bb_lower"] = roll_mean - 2 * roll_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    # --- RSI (14) ---
    delta = pd.Series(c).diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - 100 / (1 + rs)

    # --- MACD (12, 26, 9) ---
    e12 = ema(c, 12)
    e26 = ema(c, 26)
    macd_line   = e12 - e26
    signal_line = ema(np.nan_to_num(macd_line), 9)
    df["macd"]        = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"]   = macd_line - signal_line

    # --- ADX / DI (14) ---
    tr   = np.zeros(n)
    dmp  = np.zeros(n)
    dmm  = np.zeros(n)
    for i in range(1, n):
        hl = h[i] - l[i]
        hpc= abs(h[i] - c[i-1])
        lpc= abs(l[i] - c[i-1])
        tr[i]  = max(hl, hpc, lpc)
        dmp[i] = max(h[i] - h[i-1], 0) if (h[i] - h[i-1]) > (l[i-1] - l[i]) else 0
        dmm[i] = max(l[i-1] - l[i], 0) if (l[i-1] - l[i]) > (h[i] - h[i-1]) else 0

    def wilder(arr, p):
        out = np.full(len(arr), np.nan)
        out[p] = sum(arr[1:p+1])
        for i in range(p+1, len(arr)):
            out[i] = out[i-1] - out[i-1]/p + arr[i]
        return out

    atr14  = wilder(tr,  14)
    dmp14  = wilder(dmp, 14)
    dmm14  = wilder(dmm, 14)
    di_pos = 100 * dmp14 / np.where(atr14==0, 1, atr14)
    di_neg = 100 * dmm14 / np.where(atr14==0, 1, atr14)
    dx     = 100 * np.abs(di_pos - di_neg) / np.where((di_pos+di_neg)==0, 1, (di_pos+di_neg))
    adx    = wilder(dx, 14)

    df["adx"]    = adx
    df["di_pos"] = di_pos
    df["di_neg"] = di_neg

    # --- Volume MA ---
    df["vol_ma"] = pd.Series(df["volume"].values).rolling(20).mean().values

    # --- ATR ---
    df["atr"] = atr14

    return df


# ─────────────────────────────────────────────
# MARKET REGIME DETECTION
# ─────────────────────────────────────────────
def detect_regime(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    adx    = last.get("adx", 20)
    di_pos = last.get("di_pos", 20)
    di_neg = last.get("di_neg", 20)
    rsi    = last.get("rsi", 50)
    bb_w   = last.get("bb_width", 0.03)
    ema9   = last.get("ema9",  last["close"])
    ema21  = last.get("ema21", last["close"])
    ema50  = last.get("ema50", last["close"])
    close  = last["close"]
    macd_h = last.get("macd_hist", 0)

    adx = adx if not np.isnan(adx) else 20

    # Regime logic
    if adx < 22 or bb_w < 0.015:
        regime = "SIDEWAY"
        strength = "YẾU" if adx < 18 else "VỪA"
    elif di_pos > di_neg:
        regime = "UPTREND"
        strength = "MẠNH" if adx > 35 else "VỪA"
    else:
        regime = "DOWNTREND"
        strength = "MẠNH" if adx > 35 else "VỪA"

    # Signal generation
    signals = []
    # EMA cross
    if ema9 > ema21 and ema21 > ema50:
        signals.append(("🟢", "EMA xếp chuẩn LONG", "BUY"))
    elif ema9 < ema21 and ema21 < ema50:
        signals.append(("🔴", "EMA xếp chuẩn SHORT", "SELL"))

    # RSI
    if rsi < 30:
        signals.append(("🟢", f"RSI quá bán ({rsi:.1f})", "BUY"))
    elif rsi > 70:
        signals.append(("🔴", f"RSI quá mua ({rsi:.1f})", "SELL"))

    # MACD hist flip
    prev_hist = df.iloc[-2].get("macd_hist", 0) if len(df) > 1 else 0
    if prev_hist < 0 < macd_h:
        signals.append(("🟢", "MACD cắt lên", "BUY"))
    elif prev_hist > 0 > macd_h:
        signals.append(("🔴", "MACD cắt xuống", "SELL"))

    # Breakout from sideway
    bb_upper = last.get("bb_upper", close)
    bb_lower = last.get("bb_lower", close)
    if close > bb_upper:
        signals.append(("🚀", "Phá BB trên – Breakout UP", "BUY"))
    elif close < bb_lower:
        signals.append(("💥", "Phá BB dưới – Breakout DOWN", "SELL"))

    # Squeeze warning
    hist_bb_w = df["bb_width"].dropna().tail(50)
    if len(hist_bb_w) > 10 and bb_w < hist_bb_w.quantile(0.15):
        signals.append(("⚡", "BB Squeeze – Chuẩn bị bứt phá!", "WATCH"))

    return {
        "regime": regime,
        "strength": strength,
        "adx": adx,
        "di_pos": di_pos,
        "di_neg": di_neg,
        "rsi": rsi,
        "bb_width": bb_w,
        "ema9": ema9,
        "ema21": ema21,
        "ema50": ema50,
        "close": close,
        "signals": signals,
        "macd_hist": macd_h,
    }


# ─────────────────────────────────────────────
# CANDLESTICK CHART BUILDER
# ─────────────────────────────────────────────
COLORS = {
    "bg":       "#0a0e1a",
    "grid":     "#1e2d4a",
    "candle_up":"#00e676",
    "candle_dn":"#ff5252",
    "ema9":     "#f59e0b",
    "ema21":    "#38bdf8",
    "ema50":    "#a78bfa",
    "bb":       "#475569",
    "bb_fill":  "rgba(71,85,105,0.08)",
    "vol_up":   "rgba(0,230,118,0.55)",
    "vol_dn":   "rgba(255,82,82,0.55)",
    "macd_pos": "#00e676",
    "macd_neg": "#ff5252",
    "macd_sig": "#ffd600",
    "rsi":      "#38bdf8",
    "adx":      "#f59e0b",
    "di_pos":   "#00e676",
    "di_neg":   "#ff5252",
}

def build_chart(df: pd.DataFrame, title: str, regime_info: dict) -> go.Figure:
    df = df.copy().dropna(subset=["ema21"])
    n  = min(100, len(df))
    df = df.iloc[-n:]

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.52, 0.15, 0.17, 0.16],
        vertical_spacing=0.01,
    )

    # ── Candlestick ──
    colors_up = [COLORS["candle_up"] if c >= o else COLORS["candle_dn"]
                 for c, o in zip(df["close"], df["open"])]

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=COLORS["candle_up"],
        decreasing_line_color=COLORS["candle_dn"],
        increasing_fillcolor=COLORS["candle_up"],
        decreasing_fillcolor=COLORS["candle_dn"],
        line_width=1, name="OHLC",
    ), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], line=dict(color=COLORS["bb"], width=1, dash="dot"), name="BB Upper", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], line=dict(color=COLORS["bb"], width=1, dash="dot"), fill="tonexty", fillcolor=COLORS["bb_fill"], name="BB Lower", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_mid"],   line=dict(color=COLORS["bb"], width=0.8), name="BB Mid", showlegend=False), row=1, col=1)

    # EMAs
    for col, color, label in [("ema9","#f59e0b","EMA9"), ("ema21","#38bdf8","EMA21"), ("ema50","#a78bfa","EMA50")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], line=dict(color=color, width=1.5), name=label), row=1, col=1)

    # ── Volume ──
    vol_colors = [COLORS["vol_up"] if c >= o else COLORS["vol_dn"]
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=vol_colors, name="Volume", showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["vol_ma"], line=dict(color="#ffd600", width=1.2), name="Vol MA", showlegend=False), row=2, col=1)

    # ── MACD ──
    hist_colors = [COLORS["macd_pos"] if v >= 0 else COLORS["macd_neg"] for v in df["macd_hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], marker_color=hist_colors, name="MACD Hist", showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"],        line=dict(color="#38bdf8", width=1.2), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], line=dict(color=COLORS["macd_sig"], width=1.2), name="Signal"), row=3, col=1)
    fig.add_hline(y=0, line_color=COLORS["grid"], line_width=0.8, row=3, col=1)

    # ── RSI ──
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], line=dict(color=COLORS["rsi"], width=1.5), name="RSI"), row=4, col=1)
    fig.add_hline(y=70, line_color=COLORS["candle_dn"], line_width=0.8, line_dash="dot", row=4, col=1)
    fig.add_hline(y=30, line_color=COLORS["candle_up"], line_width=0.8, line_dash="dot", row=4, col=1)
    fig.add_hline(y=50, line_color=COLORS["grid"],      line_width=0.6, row=4, col=1)

    # ── Layout ──
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        margin=dict(l=0, r=0, t=36, b=0),
        height=580,
        title=dict(text=title, font=dict(family="JetBrains Mono", size=13, color="#64748b"), x=0.01),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10, color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    for i in range(1, 5):
        fig.update_xaxes(row=i, col=1, gridcolor=COLORS["grid"], showgrid=True, zeroline=False)
        fig.update_yaxes(row=i, col=1, gridcolor=COLORS["grid"], showgrid=True, zeroline=False, tickfont=dict(size=9, color="#475569"))

    fig.update_yaxes(row=4, col=1, range=[0, 100])

    return fig


# ─────────────────────────────────────────────
# TRADE HISTORY HELPERS
# ─────────────────────────────────────────────
def add_trade(direction, entry, tp, sl, size, note=""):
    trade = {
        "id":        len(st.session_state.trade_history) + 1,
        "time":      datetime.now().strftime("%H:%M:%S"),
        "date":      datetime.now().strftime("%d/%m"),
        "direction": direction,
        "entry":     entry,
        "tp":        tp,
        "sl":        sl,
        "size":      size,
        "status":    "OPEN",
        "pnl":       0.0,
        "note":      note,
    }
    st.session_state.trade_history.insert(0, trade)


def close_trade(idx, current_price):
    t = st.session_state.trade_history[idx]
    if t["status"] != "OPEN":
        return
    mult = 1 if t["direction"] == "LONG" else -1
    pnl  = (current_price - t["entry"]) * mult * t["size"] * 100_000  # VND ~
    t["status"]     = "CLOSED"
    t["exit_price"] = current_price
    t["pnl"]        = pnl
    t["close_time"] = datetime.now().strftime("%H:%M:%S")


def render_trade_history(current_price: float):
    if not st.session_state.trade_history:
        st.markdown('<div style="color:#475569;font-family:JetBrains Mono,monospace;font-size:12px;padding:12px">Chưa có lệnh nào</div>', unsafe_allow_html=True)
        return

    open_pnl  = sum(
        ((current_price - t["entry"]) * (1 if t["direction"]=="LONG" else -1) * t["size"])
        for t in st.session_state.trade_history if t["status"]=="OPEN"
    )
    total_pnl = sum(t.get("pnl", 0) for t in st.session_state.trade_history if t["status"]=="CLOSED")

    col1, col2 = st.columns(2)
    pnl_color = "green" if total_pnl >= 0 else "red"
    opnl_color= "green" if open_pnl >= 0 else "red"
    col1.markdown(f'<div class="metric-box"><div class="metric-label">P&L Đã đóng</div><div class="metric-value {pnl_color}">{total_pnl:+,.0f} đ</div></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-box"><div class="metric-label">P&L Đang mở</div><div class="metric-value {opnl_color}">{open_pnl:+.2f} pt</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    for i, t in enumerate(st.session_state.trade_history):
        dir_color  = "green"  if t["direction"]=="LONG"   else "red"
        stat_color = "#ffd600" if t["status"]=="OPEN" else "#64748b"
        live_pnl   = ""
        if t["status"] == "OPEN":
            mult   = 1 if t["direction"]=="LONG" else -1
            lp     = (current_price - t["entry"]) * mult * t["size"]
            lp_col = "green" if lp >= 0 else "red"
            live_pnl = f'<span class="{lp_col}">{lp:+.2f}pt</span>'

        exit_info = f'→ {t.get("exit_price",""):.2f}' if t["status"]=="CLOSED" else ""
        tp_sl = f'TP:{t["tp"]:.2f} | SL:{t["sl"]:.2f}'

        st.markdown(f"""
        <div style="background:#111827;border:1px solid #1e2d4a;border-radius:6px;padding:10px 14px;margin-bottom:6px;font-family:'JetBrains Mono',monospace;font-size:11px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span><b style="color:{('var(--green)' if t['direction']=='LONG' else '#ff5252')};font-size:13px">#{t['id']} {t['direction']}</b>
              &nbsp;<span style="color:#64748b">{t['date']} {t['time']}</span></span>
            <span style="color:{stat_color};font-weight:700">{t['status']}</span>
          </div>
          <div style="display:flex;justify-content:space-between;color:#94a3b8">
            <span>Entry: <b style="color:#f1f5f9">{t['entry']:.2f}</b> {exit_info} | {t['size']} HĐ</span>
            <span>{live_pnl}</span>
          </div>
          <div style="color:#475569;margin-top:3px">{tp_sl}</div>
        </div>
        """, unsafe_allow_html=True)

        if t["status"] == "OPEN":
            if st.button(f"Đóng #{t['id']}", key=f"close_{i}"):
                close_trade(i, current_price)
                st.rerun()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700;color:#38bdf8;padding:8px 0 16px">⚡ VN30F TERMINAL</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">⚙️ CÀI ĐẶT</div>', unsafe_allow_html=True)
    symbol   = st.selectbox("Hợp đồng", ["VN30F2506","VN30F2509","VN30F2512"], index=0)
    auto_refresh = st.toggle("🔄 Tự động cập nhật", value=True)
    refresh_sec  = st.slider("Chu kỳ (giây)", 10, 120, 30) if auto_refresh else 30

    st.markdown('<div class="section-header">📐 QUẢN LÝ RỦI RO</div>', unsafe_allow_html=True)
    lot_size  = st.number_input("Số hợp đồng", min_value=1, max_value=50, value=1)
    tp_points = st.number_input("TP (điểm)", min_value=1.0, max_value=50.0, value=8.0, step=0.5)
    sl_points = st.number_input("SL (điểm)", min_value=1.0, max_value=30.0, value=4.0, step=0.5)
    rr_ratio  = tp_points / sl_points
    st.markdown(f'<div style="color:#ffd600;font-family:JetBrains Mono,monospace;font-size:12px">R:R = 1 : {rr_ratio:.1f}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">📊 HIỂN THỊ</div>', unsafe_allow_html=True)
    show_ema = st.toggle("EMA 9/21/50", value=True)
    show_bb  = st.toggle("Bollinger Bands", value=True)

    st.markdown("---")
    st.markdown('<div style="font-size:10px;color:#334155;font-family:JetBrains Mono,monospace">⚠️ Đây là demo mô phỏng<br>Dữ liệu thực: kết nối API broker</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# AUTO-REFRESH LOGIC
# ─────────────────────────────────────────────
if auto_refresh:
    elapsed = (datetime.now() - st.session_state.last_refresh).seconds
    if elapsed >= refresh_sec:
        st.session_state.seed  = random.randint(0, 9999)
        st.session_state.last_refresh = datetime.now()

# ─────────────────────────────────────────────
# BUILD DATA
# ─────────────────────────────────────────────
df1 = generate_ohlcv(tf_minutes=1, n_bars=300, seed=st.session_state.seed)
df5 = generate_ohlcv(tf_minutes=5, n_bars=200, seed=st.session_state.seed)
df1 = add_indicators(df1)
df5 = add_indicators(df5)

current_price = df1["close"].iloc[-1]
prev_close    = df1["close"].iloc[-2]
regime1       = detect_regime(df1)
regime5       = detect_regime(df5)


# ─────────────────────────────────────────────
# HEADER ROW
# ─────────────────────────────────────────────
h1, h2, h3, h4, h5, h6 = st.columns([2.2, 1.5, 1.4, 1.4, 1.4, 1.4])

price_chg  = current_price - prev_close
pct_chg    = price_chg / prev_close * 100
price_col  = "green" if price_chg >= 0 else "red"
price_icon = "▲" if price_chg >= 0 else "▼"

h1.markdown(f"""
<div class="metric-box">
  <div class="metric-label">{symbol}</div>
  <div class="metric-value white" style="font-size:26px">{current_price:.2f}</div>
  <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:{'#00e676' if price_chg>=0 else '#ff5252'}">
    {price_icon} {price_chg:+.2f} ({pct_chg:+.2f}%)
  </div>
</div>
""", unsafe_allow_html=True)

regime_color = {"UPTREND":"#00e676","DOWNTREND":"#ff5252","SIDEWAY":"#ffd600"}.get(regime5["regime"],"#64748b")
h2.markdown(f"""
<div class="metric-box">
  <div class="metric-label">Xu hướng 5P</div>
  <div class="metric-value" style="color:{regime_color};font-size:15px">{regime5['regime']}</div>
  <div style="font-size:10px;color:#64748b;font-family:'JetBrains Mono',monospace">ADX {regime5['adx']:.1f} | {regime5['strength']}</div>
</div>
""", unsafe_allow_html=True)

h3.markdown(f"""
<div class="metric-box">
  <div class="metric-label">RSI (1P)</div>
  <div class="metric-value {'green' if regime1['rsi']<40 else 'red' if regime1['rsi']>60 else 'yellow'}">{regime1['rsi']:.1f}</div>
  <div style="font-size:10px;color:#64748b;font-family:'JetBrains Mono',monospace">
    {'Quá bán' if regime1['rsi']<30 else 'Quá mua' if regime1['rsi']>70 else 'Trung tính'}
  </div>
</div>
""", unsafe_allow_html=True)

h4.markdown(f"""
<div class="metric-box">
  <div class="metric-label">EMA 9/21</div>
  <div class="metric-value {'green' if regime1['ema9']>regime1['ema21'] else 'red'}" style="font-size:13px">
    {'BULL ▲' if regime1['ema9']>regime1['ema21'] else 'BEAR ▼'}
  </div>
  <div style="font-size:10px;color:#64748b;font-family:'JetBrains Mono',monospace">{regime1['ema9']:.2f} / {regime1['ema21']:.2f}</div>
</div>
""", unsafe_allow_html=True)

h5.markdown(f"""
<div class="metric-box">
  <div class="metric-label">DI+ / DI-</div>
  <div class="metric-value" style="font-size:13px">
    <span class="green">{regime1['di_pos']:.1f}</span> / <span class="red">{regime1['di_neg']:.1f}</span>
  </div>
  <div style="font-size:10px;color:#64748b;font-family:'JetBrains Mono',monospace">ADX: {regime1['adx']:.1f}</div>
</div>
""", unsafe_allow_html=True)

vol_ratio = df1["volume"].iloc[-1] / df1["vol_ma"].iloc[-1] if df1["vol_ma"].iloc[-1] > 0 else 1
h6.markdown(f"""
<div class="metric-box">
  <div class="metric-label">Volume</div>
  <div class="metric-value {'green' if vol_ratio>1.3 else 'yellow'}" style="font-size:15px">{vol_ratio:.1f}x MA</div>
  <div style="font-size:10px;color:#64748b;font-family:'JetBrains Mono',monospace">{int(df1['volume'].iloc[-1]):,}</div>
</div>
""", unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# REGIME SIGNAL BANNER
# ─────────────────────────────────────────────
def regime_banner(r: dict, label: str):
    regime = r["regime"]
    css    = {"UPTREND":"uptrend","DOWNTREND":"downtrend","SIDEWAY":"sideway"}.get(regime,"sideway")
    icon   = {"UPTREND":"🚀","DOWNTREND":"💥","SIDEWAY":"🔄"}.get(regime,"")
    arrow  = {"UPTREND":"▲","DOWNTREND":"▼","SIDEWAY":"◈"}.get(regime,"")
    desc   = {
        "UPTREND":  "Xu hướng TĂNG – Ưu tiên BUY/LONG, chờ pullback vào EMA",
        "DOWNTREND":"Xu hướng GIẢM – Ưu tiên SELL/SHORT, chờ hồi về EMA kháng cự",
        "SIDEWAY":  "Thị trường đi ngang – Giao dịch Range, canh BB biên, chờ Breakout",
    }.get(regime,"")
    return f'<div class="signal-card {css}">{icon} [{label}] {arrow} {regime} – {r["strength"]}<br><span style="font-size:11px;font-weight:400;letter-spacing:0">{desc}</span></div>'

col_r1, col_r5 = st.columns(2)
with col_r1:
    st.markdown(regime_banner(regime1, "KHUNG 1 PHÚT"), unsafe_allow_html=True)
with col_r5:
    st.markdown(regime_banner(regime5, "KHUNG 5 PHÚT"), unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIGNALS
# ─────────────────────────────────────────────
all_sigs = [(s, "1P") for s in regime1["signals"]] + [(s, "5P") for s in regime5["signals"]]
if all_sigs:
    st.markdown('<div class="section-header">🎯 TÍN HIỆU HIỆN TẠI</div>', unsafe_allow_html=True)
    sig_cols = st.columns(min(len(all_sigs), 4))
    for idx, ((icon, desc, action), tf) in enumerate(all_sigs[:4]):
        color = "#00e676" if action=="BUY" else "#ff5252" if action=="SELL" else "#ffd600"
        sig_cols[idx % 4].markdown(f"""
        <div style="background:#111827;border:1px solid {color}33;border-left:3px solid {color};border-radius:6px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:11px;">
          <div style="color:{color};font-weight:700">{icon} {action} [{tf}]</div>
          <div style="color:#94a3b8;margin-top:3px">{desc}</div>
        </div>
        """, unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CHART TABS + TRADE PANEL
# ─────────────────────────────────────────────
chart_col, trade_col = st.columns([3, 1.1])

with chart_col:
    tab1, tab5 = st.tabs(["📊 Biểu đồ 1 Phút", "📊 Biểu đồ 5 Phút"])
    with tab1:
        fig1 = build_chart(df1, f"{symbol} · 1 Phút · {datetime.now().strftime('%H:%M:%S')}", regime1)
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
    with tab5:
        fig5 = build_chart(df5, f"{symbol} · 5 Phút · {datetime.now().strftime('%H:%M:%S')}", regime5)
        st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False})

with trade_col:
    st.markdown('<div class="section-header">🔫 VÀO LỆNH NHANH</div>', unsafe_allow_html=True)

    entry_price = st.number_input("Giá vào", value=float(f"{current_price:.2f}"), step=0.1, format="%.2f")
    tp_price    = round(entry_price + tp_points, 2)
    sl_price    = round(entry_price - sl_points, 2)

    st.markdown(f"""
    <div style="background:#111827;border:1px solid #1e2d4a;border-radius:6px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:12px;margin-bottom:10px">
      <div style="color:#64748b;margin-bottom:4px">Preview lệnh LONG:</div>
      <div>🟢 TP: <b style="color:#00e676">{tp_price:.2f}</b> (+{tp_points}đ)</div>
      <div>🔴 SL: <b style="color:#ff5252">{sl_price:.2f}</b> (-{sl_points}đ)</div>
      <div style="color:#ffd600">R:R = 1:{rr_ratio:.1f} · {lot_size} HĐ</div>
    </div>
    """, unsafe_allow_html=True)

    note = st.text_input("Ghi chú lệnh", placeholder="EMA cross, BB breakout...")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🟢 BUY / LONG", use_container_width=True):
            tp = round(entry_price + tp_points, 2)
            sl = round(entry_price - sl_points, 2)
            add_trade("LONG", entry_price, tp, sl, lot_size, note)
            st.success("✅ Vào LONG!")
            st.rerun()
    with c2:
        if st.button("🔴 SELL / SHORT", use_container_width=True):
            tp = round(entry_price - tp_points, 2)
            sl = round(entry_price + sl_points, 2)
            add_trade("SHORT", entry_price, tp, sl, lot_size, note)
            st.error("✅ Vào SHORT!")
            st.rerun()

    st.markdown('<div class="section-header" style="margin-top:14px">📋 LỊCH SỬ LỆNH</div>', unsafe_allow_html=True)

    if st.button("🗑️ Xóa lịch sử", use_container_width=True):
        st.session_state.trade_history = []
        st.rerun()

    render_trade_history(current_price)


# ─────────────────────────────────────────────
# CHEAT SHEET
# ─────────────────────────────────────────────
with st.expander("📘 HƯỚNG DẪN ĐỌC TÍN HIỆU"):
    st.markdown("""
    | Chỉ báo | Tín hiệu LONG | Tín hiệu SHORT |
    |---------|--------------|----------------|
    | **EMA 9/21/50** | EMA9 > EMA21 > EMA50 | EMA9 < EMA21 < EMA50 |
    | **RSI** | RSI < 30 (quá bán) | RSI > 70 (quá mua) |
    | **MACD** | Histogram cắt lên | Histogram cắt xuống |
    | **Bollinger Bands** | Giá phá BB dưới → hồi | Giá phá BB trên → hồi |
    | **ADX** | > 25 = xu hướng mạnh, < 20 = sideway |
    | **DI+/DI-** | DI+ > DI- = bull | DI- > DI+ = bear |

    **Chiến lược theo regime:**
    - 🔄 **SIDEWAY**: Canh mua tại BB Lower, bán tại BB Upper. SL chặt.
    - 🚀 **UPTREND**: Chỉ LONG, canh pullback về EMA21, ride trend.
    - 💥 **DOWNTREND**: Chỉ SHORT, canh hồi về EMA21, ride trend.
    - ⚡ **BB Squeeze**: Chuẩn bị breakout – chờ xác nhận hướng rồi vào.
    """)


# ─────────────────────────────────────────────
# FOOTER + AUTO-REFRESH COUNTDOWN
# ─────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
footer_l, footer_r = st.columns([3,1])
footer_l.markdown(f'<div style="font-size:10px;color:#334155;font-family:JetBrains Mono,monospace">VN30F Terminal · Dữ liệu mô phỏng · Cập nhật: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</div>', unsafe_allow_html=True)

if auto_refresh:
    remaining = max(0, refresh_sec - (datetime.now() - st.session_state.last_refresh).seconds)
    footer_r.markdown(f'<div style="font-size:10px;color:#38bdf8;font-family:JetBrains Mono,monospace;text-align:right">🔄 cập nhật sau {remaining}s</div>', unsafe_allow_html=True)
    time.sleep(1)
    st.rerun()
