import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from vnstock import stock_historical_data
import time
import random

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="VN30F Terminal PRO",
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
section[data-testid="stSidebar"] { background: #0f1526; border-right: 1px solid #1e2d4a; }
section[data-testid="stSidebar"] * { color: #c9d5e8 !important; }

/* Cards & Metric boxes */
.signal-card { border-radius: 10px; padding: 18px 22px; margin-bottom: 8px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; letter-spacing: 1px; text-align: center; }
.uptrend  { background: linear-gradient(135deg,#0d2b1e,#0f3b26); border:1.5px solid #00e676; color:#00e676; }
.downtrend{ background: linear-gradient(135deg,#2b0d0d,#3b0f0f); border:1.5px solid #ff5252; color:#ff5252; }
.sideway  { background: linear-gradient(135deg,#1a1a2b,#1e1e3b); border:1.5px solid #ffd600; color:#ffd600; }
.metric-box { background: #111827; border: 1px solid #1e2d4a; border-radius: 8px; padding: 14px 16px; text-align: center; }
.metric-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.green { color: #00e676; } .red { color: #ff5252; } .yellow { color: #ffd600; } .white { color: #f1f5f9; }

/* Section headers & Others */
.section-header { font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #475569; border-bottom: 1px solid #1e2d4a; padding-bottom: 6px; margin-bottom: 12px; }
.stButton > button { background: linear-gradient(135deg,#1e40af,#1d4ed8); color: white; border: none; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.stTabs [data-baseweb="tab"] { font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 1px; color: #64748b; }
.stTabs [aria-selected="true"] { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }
.stSelectbox > div > div, .stNumberInput > div > div > input { background: #111827; border-color: #1e2d4a; color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()


# ─────────────────────────────────────────────
# REAL DATA CONNECTION – DÙNG VNSTOCK ĐỂ LÁCH TƯỜNG LỬA
# ─────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def fetch_real_ohlcv(symbol: str, tf_minutes: int, days_back: int = 5) -> pd.DataFrame:
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        # Gọi vnstock lấy dữ liệu phái sinh
        df = stock_historical_data(symbol=symbol, start_date=start_date, end_date=today, resolution=str(tf_minutes), type='derivative')
        
        if df is not None and not df.empty:
            df = df.sort_values(by='time').reset_index(drop=True)
            df['time'] = pd.to_datetime(df['time'])
            return df.set_index("time")
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()


# ─────────────────────────────────────────────
# TECHNICAL INDICATORS
# ─────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    n = len(c)

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

    roll_mean = pd.Series(c).rolling(20).mean().values
    roll_std  = pd.Series(c).rolling(20).std().values
    df["bb_mid"]   = roll_mean
    df["bb_upper"] = roll_mean + 2 * roll_std
    df["bb_lower"] = roll_mean - 2 * roll_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    delta = pd.Series(c).diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - 100 / (1 + rs)

    e12 = ema(c, 12)
    e26 = ema(c, 26)
    macd_line   = e12 - e26
    signal_line = ema(np.nan_to_num(macd_line), 9)
    df["macd"]        = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"]   = macd_line - signal_line

    tr, dmp, dmm = np.zeros(n), np.zeros(n), np.zeros(n)
    for i in range(1, n):
        hl, hpc, lpc = h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])
        tr[i]  = max(hl, hpc, lpc)
        dmp[i] = max(h[i]-h[i-1], 0) if (h[i]-h[i-1]) > (l[i-1]-l[i]) else 0
        dmm[i] = max(l[i-1]-l[i], 0) if (l[i-1]-l[i]) > (h[i]-h[i-1]) else 0

    def wilder(arr, p):
        out = np.full(len(arr), np.nan)
        out[p] = sum(arr[1:p+1])
        for i in range(p+1, len(arr)):
            out[i] = out[i-1] - out[i-1]/p + arr[i]
        return out

    atr14, dmp14, dmm14  = wilder(tr, 14), wilder(dmp, 14), wilder(dmm, 14)
    di_pos = 100 * dmp14 / np.where(atr14==0, 1, atr14)
    di_neg = 100 * dmm14 / np.where(atr14==0, 1, atr14)
    dx     = 100 * np.abs(di_pos - di_neg) / np.where((di_pos+di_neg)==0, 1, (di_pos+di_neg))
    
    df["adx"], df["di_pos"], df["di_neg"] = wilder(dx, 14), di_pos, di_neg
    df["vol_ma"] = pd.Series(df["volume"].values).rolling(20).mean().values
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

    if adx < 22 or bb_w < 0.015:
        regime, strength = "SIDEWAY", "YẾU" if adx < 18 else "VỪA"
    elif di_pos > di_neg:
        regime, strength = "UPTREND", "MẠNH" if adx > 35 else "VỪA"
    else:
        regime, strength = "DOWNTREND", "MẠNH" if adx > 35 else "VỪA"

    signals = []
    if ema9 > ema21 > ema50: signals.append(("🟢", "EMA xếp chuẩn LONG", "BUY"))
    elif ema9 < ema21 < ema50: signals.append(("🔴", "EMA xếp chuẩn SHORT", "SELL"))

    if rsi < 30: signals.append(("🟢", f"RSI quá bán ({rsi:.1f})", "BUY"))
    elif rsi > 70: signals.append(("🔴", f"RSI quá mua ({rsi:.1f})", "SELL"))

    prev_hist = df.iloc[-2].get("macd_hist", 0) if len(df) > 1 else 0
    if prev_hist < 0 < macd_h: signals.append(("🟢", "MACD cắt lên", "BUY"))
    elif prev_hist > 0 > macd_h: signals.append(("🔴", "MACD cắt xuống", "SELL"))

    bb_upper, bb_lower = last.get("bb_upper", close), last.get("bb_lower", close)
    if close > bb_upper: signals.append(("🚀", "Phá BB trên – Breakout UP", "BUY"))
    elif close < bb_lower: signals.append(("💥", "Phá BB dưới – Breakout DOWN", "SELL"))

    return {
        "regime": regime, "strength": strength, "adx": adx, "di_pos": di_pos, "di_neg": di_neg,
        "rsi": rsi, "bb_width": bb_w, "ema9": ema9, "ema21": ema21, "ema50": ema50,
        "close": close, "signals": signals, "macd_hist": macd_h,
    }


# ─────────────────────────────────────────────
# CANDLESTICK CHART BUILDER
# ─────────────────────────────────────────────
COLORS = {
    "bg": "#0a0e1a", "grid": "#1e2d4a", "candle_up":"#00e676", "candle_dn":"#ff5252",
    "ema9": "#f59e0b", "ema21": "#38bdf8", "ema50": "#a78bfa", "bb": "#475569", "bb_fill": "rgba(71,85,105,0.08)",
    "vol_up": "rgba(0,230,118,0.55)", "vol_dn": "rgba(255,82,82,0.55)", "macd_pos": "#00e676", "macd_neg": "#ff5252",
    "macd_sig": "#ffd600", "rsi": "#38bdf8"
}

def build_chart(df: pd.DataFrame, title: str, regime_info: dict) -> go.Figure:
    df = df.copy().dropna(subset=["ema21"])
    n  = min(100, len(df))
    df = df.iloc[-n:]

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.52, 0.15, 0.17, 0.16], vertical_spacing=0.01)

    colors_up = [COLORS["candle_up"] if c >= o else COLORS["candle_dn"] for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color=COLORS["candle_up"], decreasing_line_color=COLORS["candle_dn"],
        increasing_fillcolor=COLORS["candle_up"], decreasing_fillcolor=COLORS["candle_dn"], line_width=1, name="OHLC"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], line=dict(color=COLORS["bb"], width=1, dash="dot"), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], line=dict(color=COLORS["bb"], width=1, dash="dot"), fill="tonexty", fillcolor=COLORS["bb_fill"], showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["bb_mid"], line=dict(color=COLORS["bb"], width=0.8), showlegend=False), row=1, col=1)

    for col, color, label in [("ema9","#f59e0b","EMA9"), ("ema21","#38bdf8","EMA21"), ("ema50","#a78bfa","EMA50")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], line=dict(color=color, width=1.5), name=label), row=1, col=1)

    vol_colors = [COLORS["vol_up"] if c >= o else COLORS["vol_dn"] for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=vol_colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["vol_ma"], line=dict(color="#ffd600", width=1.2), showlegend=False), row=2, col=1)

    hist_colors = [COLORS["macd_pos"] if v >= 0 else COLORS["macd_neg"] for v in df["macd_hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], marker_color=hist_colors, showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"], line=dict(color="#38bdf8", width=1.2), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], line=dict(color=COLORS["macd_sig"], width=1.2), name="Signal"), row=3, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], line=dict(color=COLORS["rsi"], width=1.5), name="RSI"), row=4, col=1)
    fig.add_hline(y=70, line_color=COLORS["candle_dn"], line_width=0.8, line_dash="dot", row=4, col=1)
    fig.add_hline(y=30, line_color=COLORS["candle_up"], line_width=0.8, line_dash="dot", row=4, col=1)

    fig.update_layout(
        template="plotly_dark", paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        margin=dict(l=0, r=0, t=36, b=0), height=580,
        title=dict(text=title, font=dict(family="JetBrains Mono", size=13, color="#64748b"), x=0.01),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, font=dict(size=10, color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
        xaxis_rangeslider_visible=False, hovermode="x unified",
    )
    for i in range(1, 5):
        fig.update_xaxes(row=i, col=1, gridcolor=COLORS["grid"], showgrid=True, zeroline=False)
        fig.update_yaxes(row=i, col=1, gridcolor=COLORS["grid"], showgrid=True, zeroline=False, tickfont=dict(size=9, color="#475569"))

    return fig

# ─────────────────────────────────────────────
# TRADE HISTORY HELPERS
# ─────────────────────────────────────────────
def add_trade(direction, entry, tp, sl, size, note=""):
    st.session_state.trade_history.insert(0, {
        "id": len(st.session_state.trade_history) + 1, "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d/%m"), "direction": direction, "entry": entry,
        "tp": tp, "sl": sl, "size": size, "status": "OPEN", "pnl": 0.0, "note": note,
    })

def close_trade(idx, current_price):
    t = st.session_state.trade_history[idx]
    if t["status"] == "OPEN":
        t["status"], t["exit_price"] = "CLOSED", current_price
        t["pnl"] = (current_price - t["entry"]) * (1 if t["direction"] == "LONG" else -1) * t["size"] * 100_000

def render_trade_history(current_price: float):
    if not st.session_state.trade_history:
        st.markdown('<div style="color:#475569;font-size:12px;padding:12px">Chưa có lệnh nào</div>', unsafe_allow_html=True)
        return

    open_pnl = sum(((current_price - t["entry"]) * (1 if t["direction"]=="LONG" else -1) * t["size"]) for t in st.session_state.trade_history if t["status"]=="OPEN")
    total_pnl = sum(t.get("pnl", 0) for t in st.session_state.trade_history if t["status"]=="CLOSED")

    col1, col2 = st.columns(2)
    col1.markdown(f'<div class="metric-box"><div class="metric-label">P&L Đã đóng</div><div class="metric-value {"green" if total_pnl >= 0 else "red"}">{total_pnl:+,.0f} đ</div></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-box"><div class="metric-label">P&L Đang mở</div><div class="metric-value {"green" if open_pnl >= 0 else "red"}">{open_pnl:+.2f} pt</div></div>', unsafe_allow_html=True)

    for i, t in enumerate(st.session_state.trade_history):
        stat_color = "#ffd600" if t["status"]=="OPEN" else "#64748b"
        st.markdown(f"""
        <div style="background:#111827;border:1px solid #1e2d4a;border-radius:6px;padding:10px;margin-top:6px;font-family:'JetBrains Mono';font-size:11px;">
          <div style="display:flex;justify-content:space-between;">
            <span style="color:{('var(--green)' if t['direction']=='LONG' else '#ff5252')}"><b>#{t['id']} {t['direction']}</b></span>
            <span style="color:{stat_color};font-weight:700">{t['status']}</span>
          </div>
          <div style="color:#94a3b8">Entry: <b>{t['entry']:.2f}</b> | TP:{t['tp']:.2f} SL:{t['sl']:.2f}</div>
        </div>""", unsafe_allow_html=True)
        if t["status"] == "OPEN" and st.button(f"Đóng #{t['id']}", key=f"close_{i}"):
            close_trade(i, current_price)
            st.rerun()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-family:JetBrains Mono;font-size:18px;font-weight:700;color:#38bdf8;padding:8px 0 16px">⚡ VN30F TERMINAL PRO</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">⚙️ CÀI ĐẶT</div>', unsafe_allow_html=True)
    symbol = st.selectbox("Hợp đồng", ["VN30F1M", "VN30F1Q", "VN30F2Q"], index=0)
    auto_refresh = st.toggle("🔄 Tự động cập nhật", value=True)
    refresh_sec  = st.slider("Chu kỳ (giây)", 10, 120, 30) if auto_refresh else 30

    st.markdown('<div class="section-header">📐 QUẢN LÝ RỦI RO</div>', unsafe_allow_html=True)
    lot_size  = st.number_input("Số hợp đồng", min_value=1, max_value=50, value=1)
    tp_points = st.number_input("TP (điểm)", min_value=1.0, max_value=50.0, value=8.0, step=0.5)
    sl_points = st.number_input("SL (điểm)", min_value=1.0, max_value=30.0, value=4.0, step=0.5)
    
    st.markdown("---")
    st.markdown('<div style="font-size:10px;color:#00e676;font-family:JetBrains Mono">🟢 Đang kết nối API qua Vnstock</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# BUILD DATA TỪ VNSTOCK
# ─────────────────────────────────────────────
df1 = fetch_real_ohlcv(symbol, tf_minutes=1, days_back=3)
df5 = fetch_real_ohlcv(symbol, tf_minutes=5, days_back=7)

if df1.empty or df5.empty:
    st.error("❌ Không lấy được dữ liệu. Có thể do ngoài giờ giao dịch, nghỉ lễ hoặc API đang bảo trì.")
    st.stop()

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
price_chg = current_price - prev_close
pct_chg   = price_chg / prev_close * 100

h1.markdown(f"""
<div class="metric-box">
  <div class="metric-label">{symbol}</div>
  <div class="metric-value white" style="font-size:26px">{current_price:.2f}</div>
  <div style="font-size:12px;color:{'#00e676' if price_chg>=0 else '#ff5252'}">
    {'▲' if price_chg>=0 else '▼'} {price_chg:+.2f} ({pct_chg:+.2f}%)
  </div>
</div>""", unsafe_allow_html=True)

h2.markdown(f'<div class="metric-box"><div class="metric-label">Xu hướng 5P</div><div class="metric-value" style="color:{"#00e676" if regime5["regime"]=="UPTREND" else "#ff5252" if regime5["regime"]=="DOWNTREND" else "#ffd600"}">{regime5["regime"]}</div><div style="font-size:10px;color:#64748b">ADX {regime5["adx"]:.1f}</div></div>', unsafe_allow_html=True)
h3.markdown(f'<div class="metric-box"><div class="metric-label">RSI (1P)</div><div class="metric-value {"green" if regime1["rsi"]<40 else "red" if regime1["rsi"]>60 else "yellow"}">{regime1["rsi"]:.1f}</div></div>', unsafe_allow_html=True)
h4.markdown(f'<div class="metric-box"><div class="metric-label">EMA 9/21</div><div class="metric-value {"green" if regime1["ema9"]>regime1["ema21"] else "red"}">{"BULL ▲" if regime1["ema9"]>regime1["ema21"] else "BEAR ▼"}</div></div>', unsafe_allow_html=True)
h5.markdown(f'<div class="metric-box"><div class="metric-label">DI+ / DI-</div><div class="metric-value"><span class="green">{regime1["di_pos"]:.1f}</span> / <span class="red">{regime1["di_neg"]:.1f}</span></div></div>', unsafe_allow_html=True)
h6.markdown(f'<div class="metric-box"><div class="metric-label">Volume</div><div class="metric-value yellow">{int(df1["volume"].iloc[-1]):,}</div></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# CHART TABS + TRADE PANEL
# ─────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
chart_col, trade_col = st.columns([3, 1.1])

with chart_col:
    tab1, tab5 = st.tabs(["📊 Biểu đồ 1 Phút (Thực)", "📊 Biểu đồ 5 Phút (Thực)"])
    with tab1:
        st.plotly_chart(build_chart(df1, f"{symbol} · 1P", regime1), use_container_width=True, config={"displayModeBar": False})
    with tab5:
        st.plotly_chart(build_chart(df5, f"{symbol} · 5P", regime5), use_container_width=True, config={"displayModeBar": False})

with trade_col:
    st.markdown('<div class="section-header">🔫 VÀO LỆNH NHANH</div>', unsafe_allow_html=True)
    entry_price = st.number_input("Giá vào", value=float(f"{current_price:.2f}"), step=0.1)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🟢 BUY", use_container_width=True):
            add_trade("LONG", entry_price, entry_price+tp_points, entry_price-sl_points, lot_size)
            st.rerun()
    with c2:
        if st.button("🔴 SELL", use_container_width=True):
            add_trade("SHORT", entry_price, entry_price-tp_points, entry_price+sl_points, lot_size)
            st.rerun()

    st.markdown('<div class="section-header" style="margin-top:14px">📋 LỊCH SỬ LỆNH</div>', unsafe_allow_html=True)
    if st.button("🗑️ Xóa", use_container_width=True):
        st.session_state.trade_history = []
        st.rerun()
    render_trade_history(current_price)

# ─────────────────────────────────────────────
# AUTO-REFRESH
# ─────────────────────────────────────────────
if auto_refresh:
    elapsed = (datetime.now() - st.session_state.last_refresh).seconds
    if elapsed >= refresh_sec:
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    time.sleep(1)
    st.rerun()
