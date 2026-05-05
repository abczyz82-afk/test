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

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; background-color: #0a0e1a; color: #e2e8f0; }
.stApp { background: #0a0e1a; }
section[data-testid="stSidebar"] { background: #0f1526; border-right: 1px solid #1e2d4a; }
section[data-testid="stSidebar"] * { color: #c9d5e8 !important; }
.signal-card { border-radius: 10px; padding: 18px 22px; margin-bottom: 8px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 15px; text-align: center; }
.uptrend  { background: linear-gradient(135deg,#0d2b1e,#0f3b26); border:1.5px solid #00e676; color:#00e676; }
.downtrend{ background: linear-gradient(135deg,#2b0d0d,#3b0f0f); border:1.5px solid #ff5252; color:#ff5252; }
.sideway  { background: linear-gradient(135deg,#1a1a2b,#1e1e3b); border:1.5px solid #ffd600; color:#ffd600; }
.metric-box { background: #111827; border: 1px solid #1e2d4a; border-radius: 8px; padding: 14px 16px; text-align: center; }
.metric-label { font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; }
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.green { color: #00e676; } .red { color: #ff5252; } .yellow { color: #ffd600; } .white { color: #f1f5f9; }
.section-header { font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #475569; border-bottom: 1px solid #1e2d4a; padding-bottom: 6px; margin-bottom: 12px; }
.stButton > button { background: linear-gradient(135deg,#1e40af,#1d4ed8); color: white; border: none; border-radius: 6px; font-weight: 600; }
.stTabs [data-baseweb="tab"] { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #64748b; }
.stTabs [aria-selected="true"] { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }
.stSelectbox > div > div, .stNumberInput > div > div > input { background: #111827; border-color: #1e2d4a; color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)

if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# ─────────────────────────────────────────────
# DATA FETCHING (VNSTOCK)
# ─────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def fetch_real_ohlcv(symbol: str, tf_minutes: int, days_back: int = 5) -> pd.DataFrame:
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        df = stock_historical_data(symbol=symbol, start_date=start_date, end_date=today, resolution=str(tf_minutes), type='derivative')
        if df is not None and not df.empty:
            df = df.sort_values(by='time').reset_index(drop=True)
            df['time'] = pd.to_datetime(df['time'])
            return df.set_index("time")
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# ─────────────────────────────────────────────
# INDICATORS & SIGNALS CALCULATION
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
        for i in range(period, len(arr)): result[i] = arr[i] * k + result[i-1] * (1 - k)
        return result

    df["ema9"], df["ema21"], df["ema50"] = ema(c, 9), ema(c, 21), ema(c, 50)
    roll_mean = pd.Series(c).rolling(20).mean().values
    roll_std  = pd.Series(c).rolling(20).std().values
    df["bb_mid"], df["bb_upper"], df["bb_lower"] = roll_mean, roll_mean + 2 * roll_std, roll_mean - 2 * roll_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    delta = pd.Series(c).diff()
    rs = delta.clip(lower=0).rolling(14).mean() / (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    df["rsi"] = 100 - 100 / (1 + rs)

    df["macd"] = ema(c, 12) - ema(c, 26)
    df["macd_signal"] = ema(np.nan_to_num(df["macd"].values), 9)
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Calculate exact Buy/Sell Signals for Chart Markers
    df["ema_cross_up"] = (df["ema9"] > df["ema21"]) & (df["ema9"].shift(1) <= df["ema21"].shift(1))
    df["ema_cross_dn"] = (df["ema9"] < df["ema21"]) & (df["ema9"].shift(1) >= df["ema21"].shift(1))
    df["buy_signal"] = df["ema_cross_up"] & (df["rsi"] > 40)
    df["sell_signal"] = df["ema_cross_dn"] & (df["rsi"] < 60)

    tr, dmp, dmm = np.zeros(n), np.zeros(n), np.zeros(n)
    for i in range(1, n):
        tr[i]  = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
        dmp[i] = max(h[i]-h[i-1], 0) if (h[i]-h[i-1]) > (l[i-1]-l[i]) else 0
        dmm[i] = max(l[i-1]-l[i], 0) if (l[i-1]-l[i]) > (h[i]-h[i-1]) else 0

    def wilder(arr, p):
        out = np.full(len(arr), np.nan)
        out[p] = sum(arr[1:p+1])
        for i in range(p+1, len(arr)): out[i] = out[i-1] - out[i-1]/p + arr[i]
        return out

    atr14, dmp14, dmm14  = wilder(tr, 14), wilder(dmp, 14), wilder(dmm, 14)
    di_pos, di_neg = 100 * dmp14 / np.where(atr14==0, 1, atr14), 100 * dmm14 / np.where(atr14==0, 1, atr14)
    df["adx"] = wilder(100 * np.abs(di_pos - di_neg) / np.where((di_pos+di_neg)==0, 1, (di_pos+di_neg)), 14)
    df["di_pos"], df["di_neg"], df["vol_ma"] = di_pos, di_neg, pd.Series(df["volume"].values).rolling(20).mean().values

    return df

def detect_regime(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    adx, di_pos, di_neg, rsi, bb_w, ema9, ema21, ema50, close, macd_h = (
        last.get("adx", 20), last.get("di_pos", 20), last.get("di_neg", 20), last.get("rsi", 50),
        last.get("bb_width", 0.03), last.get("ema9", last["close"]), last.get("ema21", last["close"]),
        last.get("ema50", last["close"]), last["close"], last.get("macd_hist", 0)
    )
    if np.isnan(adx): adx = 20

    if adx < 22 or bb_w < 0.015: regime, strength = "SIDEWAY", "YẾU" if adx < 18 else "VỪA"
    elif di_pos > di_neg: regime, strength = "UPTREND", "MẠNH" if adx > 35 else "VỪA"
    else: regime, strength = "DOWNTREND", "MẠNH" if adx > 35 else "VỪA"

    signals = []
    if ema9 > ema21 > ema50: signals.append(("🟢", "EMA xếp chuẩn LONG", "BUY"))
    elif ema9 < ema21 < ema50: signals.append(("🔴", "EMA xếp chuẩn SHORT", "SELL"))
    if rsi < 30: signals.append(("🟢", f"RSI quá bán ({rsi:.1f})", "BUY"))
    elif rsi > 70: signals.append(("🔴", f"RSI quá mua ({rsi:.1f})", "SELL"))
    
    return {
        "regime": regime, "strength": strength, "adx": adx, "di_pos": di_pos, "di_neg": di_neg,
        "rsi": rsi, "ema9": ema9, "ema21": ema21, "signals": signals
    }

# ─────────────────────────────────────────────
# SUPER CHART BUILDER (WITH TOGGLES & MARKERS)
# ─────────────────────────────────────────────
COLORS = {
    "bg": "#0a0e1a", "grid": "#1e2d4a", "candle_up":"#00e676", "candle_dn":"#ff5252",
    "ema9": "#f59e0b", "ema21": "#38bdf8", "ema50": "#a78bfa", "bb": "#475569", "bb_fill": "rgba(71,85,105,0.08)"
}

def build_chart(df: pd.DataFrame, title: str, show_ema: bool, show_bb: bool, show_signals: bool, show_trades: bool) -> go.Figure:
    df = df.copy().dropna(subset=["ema21"])
    df = df.iloc[-100:] # Show last 100 candles

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.52, 0.15, 0.17, 0.16], vertical_spacing=0.01)

    # 1. CANDLESTICKS
    fig.add_trace(go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color=COLORS["candle_up"], decreasing_line_color=COLORS["candle_dn"],
        increasing_fillcolor=COLORS["candle_up"], decreasing_fillcolor=COLORS["candle_dn"], line_width=1, name="OHLC"), row=1, col=1)

    # 2. TOGGLE: BOLLINGER BANDS
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], line=dict(color=COLORS["bb"], width=1, dash="dot"), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], line=dict(color=COLORS["bb"], width=1, dash="dot"), fill="tonexty", fillcolor=COLORS["bb_fill"], showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_mid"], line=dict(color=COLORS["bb"], width=0.8), showlegend=False), row=1, col=1)

    # 3. TOGGLE: EMAs
    if show_ema:
        for col, color, label in [("ema9","#f59e0b","EMA9"), ("ema21","#38bdf8","EMA21"), ("ema50","#a78bfa","EMA50")]:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], line=dict(color=color, width=1.5), name=label), row=1, col=1)

    # 4. TOGGLE: BOT SIGNALS (Mũi tên Mua/Bán trên biểu đồ)
    if show_signals:
        buys = df[df["buy_signal"] == True]
        sells = df[df["sell_signal"] == True]
        if not buys.empty:
            fig.add_trace(go.Scatter(x=buys.index, y=buys["low"] - 1.5, mode="markers", marker=dict(symbol="triangle-up", size=14, color="#00e676"), name="Tín hiệu MUA"), row=1, col=1)
        if not sells.empty:
            fig.add_trace(go.Scatter(x=sells.index, y=sells["high"] + 1.5, mode="markers", marker=dict(symbol="triangle-down", size=14, color="#ff5252"), name="Tín hiệu BÁN"), row=1, col=1)

    # 5. TOGGLE: ACTIVE TRADES (Kẻ ngang Entry, TP, SL)
    if show_trades and "trade_history" in st.session_state:
        for t in st.session_state.trade_history:
            if t["status"] == "OPEN":
                c = "#00e676" if t["direction"] == "LONG" else "#ff5252"
                fig.add_hline(y=t["entry"], line_color=c, line_width=1.5, line_dash="solid", row=1, col=1, annotation_text=f"ENTRY {t['direction']}", annotation_position="right", annotation_font_color=c)
                fig.add_hline(y=t["tp"], line_color="#00e676", line_width=1, line_dash="dash", row=1, col=1, annotation_text=f"TP {t['tp']}", annotation_position="right", annotation_font_color="#00e676")
                fig.add_hline(y=t["sl"], line_color="#ff5252", line_width=1, line_dash="dash", row=1, col=1, annotation_text=f"SL {t['sl']}", annotation_position="right", annotation_font_color="#ff5252")

    # Volume, MACD, RSI
    v_colors = ["rgba(0,230,118,0.55)" if c >= o else "rgba(255,82,82,0.55)" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=v_colors, showlegend=False), row=2, col=1)
    
    m_colors = ["#00e676" if v >= 0 else "#ff5252" for v in df["macd_hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], marker_color=m_colors, showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"], line=dict(color="#38bdf8", width=1.2), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], line=dict(color="#ffd600", width=1.2), name="Signal"), row=3, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], line=dict(color="#38bdf8", width=1.5), name="RSI"), row=4, col=1)
    fig.add_hline(y=70, line_color="#ff5252", line_width=0.8, line_dash="dot", row=4, col=1)
    fig.add_hline(y=30, line_color="#00e676", line_width=0.8, line_dash="dot", row=4, col=1)

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
# TRADE LOGIC
# ─────────────────────────────────────────────
def add_trade(direction, entry, tp, sl, size):
    st.session_state.trade_history.insert(0, {
        "id": len(st.session_state.trade_history) + 1, "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d/%m"), "direction": direction, "entry": entry,
        "tp": tp, "sl": sl, "size": size, "status": "OPEN", "pnl": 0.0
    })

def close_trade(idx, current_price):
    t = st.session_state.trade_history[idx]
    if t["status"] == "OPEN":
        t["status"], t["exit_price"] = "CLOSED", current_price
        t["pnl"] = (current_price - t["entry"]) * (1 if t["direction"] == "LONG" else -1) * t["size"] * 100_000

# ─────────────────────────────────────────────
# SIDEBAR CONTROLS
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-family:JetBrains Mono;font-size:18px;font-weight:700;color:#38bdf8;padding:8px 0 16px">⚡ VN30F TERMINAL PRO</div>', unsafe_allow_html=True)
    symbol = st.selectbox("Hợp đồng", ["VN30F1M", "VN30F1Q", "VN30F2Q"], index=0)
    auto_refresh = st.toggle("🔄 Tự động cập nhật", value=True)
    
    st.markdown('<div class="section-header">📊 BẬT / TẮT BIỂU ĐỒ</div>', unsafe_allow_html=True)
    show_ema = st.toggle("📉 Đường trung bình (EMA)", value=False)
    show_bb  = st.toggle("🌊 Dải băng Bollinger", value=False)
    show_signals = st.toggle("🎯 Tín hiệu Bot (Buy/Sell)", value=True)
    show_trades = st.toggle("🛒 Lệnh của bạn (Kẻ TP/SL)", value=True)

    st.markdown('<div class="section-header">📐 QUẢN LÝ RỦI RO</div>', unsafe_allow_html=True)
    lot_size  = st.number_input("Số hợp đồng", min_value=1, max_value=50, value=1)
    tp_points = st.number_input("TP (điểm)", min_value=1.0, max_value=50.0, value=8.0, step=0.5)
    sl_points = st.number_input("SL (điểm)", min_value=1.0, max_value=30.0, value=4.0, step=0.5)
    
    st.markdown("---")
    st.markdown('<div style="font-size:10px;color:#00e676;font-family:JetBrains Mono">🟢 Đang kết nối API qua Vnstock</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MAIN APP EXECUTION
# ─────────────────────────────────────────────
df1 = fetch_real_ohlcv(symbol, tf_minutes=1, days_back=3)
df5 = fetch_real_ohlcv(symbol, tf_minutes=5, days_back=7)

if df1.empty or df5.empty:
    st.error("❌ Không lấy được dữ liệu. Có thể do ngoài giờ giao dịch, nghỉ lễ hoặc API đang bảo trì.")
    st.stop()

df1, df5 = add_indicators(df1), add_indicators(df5)
current_price, prev_close = df1["close"].iloc[-1], df1["close"].iloc[-2]
regime1, regime5 = detect_regime(df1), detect_regime(df5)

# HEADER METRICS
h1, h2, h3, h4, h5, h6 = st.columns([2.2, 1.5, 1.4, 1.4, 1.4, 1.4])
price_chg = current_price - prev_close
h1.markdown(f'<div class="metric-box"><div class="metric-label">{symbol}</div><div class="metric-value white" style="font-size:26px">{current_price:.2f}</div><div style="font-size:12px;color:{"#00e676" if price_chg>=0 else "#ff5252"}">{"▲" if price_chg>=0 else "▼"} {price_chg:+.2f}</div></div>', unsafe_allow_html=True)
h2.markdown(f'<div class="metric-box"><div class="metric-label">Xu hướng 5P</div><div class="metric-value" style="color:{"#00e676" if regime5["regime"]=="UPTREND" else "#ff5252" if regime5["regime"]=="DOWNTREND" else "#ffd600"}">{regime5["regime"]}</div></div>', unsafe_allow_html=True)
h3.markdown(f'<div class="metric-box"><div class="metric-label">RSI (1P)</div><div class="metric-value {"green" if regime1["rsi"]<40 else "red" if regime1["rsi"]>60 else "yellow"}">{regime1["rsi"]:.1f}</div></div>', unsafe_allow_html=True)
h4.markdown(f'<div class="metric-box"><div class="metric-label">EMA 9/21</div><div class="metric-value {"green" if regime1["ema9"]>regime1["ema21"] else "red"}">{"BULL ▲" if regime1["ema9"]>regime1["ema21"] else "BEAR ▼"}</div></div>', unsafe_allow_html=True)
h5.markdown(f'<div class="metric-box"><div class="metric-label">DI+ / DI-</div><div class="metric-value"><span class="green">{regime1["di_pos"]:.1f}</span> / <span class="red">{regime1["di_neg"]:.1f}</span></div></div>', unsafe_allow_html=True)
h6.markdown(f'<div class="metric-box"><div class="metric-label">Volume</div><div class="metric-value yellow">{int(df1["volume"].iloc[-1]):,}</div></div>', unsafe_allow_html=True)

# CHART & TRADES
st.markdown("<br>", unsafe_allow_html=True)
chart_col, trade_col = st.columns([3, 1.1])

with chart_col:
    tab1, tab5 = st.tabs(["📊 Biểu đồ 1 Phút", "📊 Biểu đồ 5 Phút"])
    with tab1: st.plotly_chart(build_chart(df1, f"{symbol} · 1P", show_ema, show_bb, show_signals, show_trades), use_container_width=True, config={"displayModeBar": False})
    with tab5: st.plotly_chart(build_chart(df5, f"{symbol} · 5P", show_ema, show_bb, show_signals, show_trades), use_container_width=True, config={"displayModeBar": False})

with trade_col:
    st.markdown('<div class="section-header">🔫 VÀO LỆNH NHANH</div>', unsafe_allow_html=True)
    entry_price = st.number_input("Giá vào", value=float(f"{current_price:.2f}"), step=0.1)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🟢 BUY", use_container_width=True): add_trade("LONG", entry_price, entry_price+tp_points, entry_price-sl_points, lot_size); st.rerun()
    with c2:
        if st.button("🔴 SELL", use_container_width=True): add_trade("SHORT", entry_price, entry_price-tp_points, entry_price+sl_points, lot_size); st.rerun()

    st.markdown('<div class="section-header" style="margin-top:14px">📋 LỊCH SỬ LỆNH</div>', unsafe_allow_html=True)
    if st.button("🗑️ Xóa", use_container_width=True): st.session_state.trade_history = []; st.rerun()
    
    for i, t in enumerate(st.session_state.trade_history):
        st.markdown(f"<div style='background:#111827;border:1px solid #1e2d4a;padding:10px;margin-top:6px;font-size:11px;'><span style='color:{'#00e676' if t['direction']=='LONG' else '#ff5252'}'><b>#{t['id']} {t['direction']}</b></span> <span style='float:right;color:#ffd600'>{t['status']}</span><br><span style='color:#94a3b8'>Entry: {t['entry']:.2f} | TP:{t['tp']:.2f} SL:{t['sl']:.2f}</span></div>", unsafe_allow_html=True)
        if t["status"] == "OPEN" and st.button(f"Đóng #{t['id']}", key=f"close_{i}"): close_trade(i, current_price); st.rerun()

if auto_refresh:
    if (datetime.now() - st.session_state.last_refresh).seconds >= 30:
        st.session_state.last_refresh = datetime.now(); st.rerun()
    time.sleep(1); st.rerun()
