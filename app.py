import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
import plotly.graph_objs as go
from ta.trend import PSARIndicator, IchimokuIndicator
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator, StochasticOscillator
from datetime import datetime, timedelta

# Configurazione della pagina con tema professionale
st.set_page_config(
    page_title="Finora Pro Trading Terminal",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Iniezione CSS per stile premium
st.markdown(f"""
<style>
    :root {{
        --primary: #2e86de;
        --secondary: #0c2461;
        --success: #27ae60;
        --danger: #e74c3c;
        --warning: #f39c12;
        --dark: #2c3e50;
        --light: #ecf0f1;
    }}
    
    .stApp {{
        background: linear-gradient(135deg, #0c2461 0%, #1e3799 100%);
        color: #fff;
    }}
    
    .header-box {{
        background: linear-gradient(90deg, var(--secondary) 0%, var(--primary) 100%);
        padding: 1.5rem 2rem;
        border-radius: 0 0 20px 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        margin-bottom: 2rem;
    }}
    
    .card {{
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.18);
        border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 1.5rem;
    }}
    
    .signal-card {{
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-left: 4px solid;
    }}
    
    .signal-buy {{
        background: linear-gradient(90deg, rgba(39, 174, 96, 0.15) 0%, rgba(46, 204, 113, 0.15) 100%);
        border-left-color: var(--success);
    }}
    
    .signal-sell {{
        background: linear-gradient(90deg, rgba(231, 76, 60, 0.15) 0%, rgba(192, 57, 43, 0.15) 100%);
        border-left-color: var(--danger);
    }}
    
    .indicator-box {{
        background: rgba(0,0,0,0.2);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }}
    
    .positive {{
        color: var(--success);
        font-weight: 700;
    }}
    
    .negative {{
        color: var(--danger);
        font-weight: 700;
    }}
    
    .st-bb {{
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 1rem;
        margin-bottom: 1.5rem;
    }}
    
    .stButton>button {{
        background: linear-gradient(90deg, var(--primary) 0%, #1e90ff 100%);
        border: none;
        color: white;
        font-weight: 600;
        border-radius: 12px;
        padding: 0.8rem 1.5rem;
        transition: all 0.3s ease;
    }}
    
    .stButton>button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 7px 14px rgba(30, 144, 255, 0.3);
    }}
    
    .stSelectbox, .stTextInput, .stSlider {{
        background: rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 0.5rem 1rem;
    }}
</style>
""", unsafe_allow_html=True)

# Header con branding Finora
st.markdown("""
<div class="header-box">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; color: white; font-weight: 700;">🚀 FINORA PRO TRADING TERMINAL</h1>
            <p style="margin: 0; font-size: 1.2rem; opacity: 0.9;">Smarter trades, less stress. Let Finora lead the way in all markets!</p>
        </div>
        <a href="https://t.me/FinoraEN_Bot" target="_blank">
            <button style="background: linear-gradient(90deg, #f39c12 0%, #f1c40f 100%); 
                        border: none; color: #2c3e50; padding: 0.8rem 1.5rem; 
                        border-radius: 12px; font-weight: 600; cursor: pointer;
                        display: flex; align-items: center; gap: 8px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                </svg>
                Connect to Telegram Bot
            </button>
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar - Configurazione trading
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1.5rem;">
        <h3 style="color: #3498db; margin-bottom: 0.5rem;">⚙️ TRADING PARAMETERS</h3>
        <div style="background: linear-gradient(90deg, #2e86de, #3498db); height: 3px; width: 50%; margin: 0 auto;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Selezione asset
    asset_type = st.selectbox("ASSET TYPE", ["Crypto", "Forex", "Stocks"], index=0)
    
    # Per Crypto
    if asset_type == "Crypto":
        @st.cache_data(ttl=3600, show_spinner="Fetching market data...")
        def get_coinbase_products():
            url = "https://api.exchange.coinbase.com/products"
            resp = requests.get(url)
            data = resp.json()
            pairs = [p["id"] for p in data if p["quote_currency"] == "USD" and p["trading_disabled"] is False]
            return sorted(pairs)
        
        coin_pairs = get_coinbase_products()
        search = st.text_input("🔍 Search Crypto (BTC, ETH, etc.)", "")
        filtered_pairs = [c for c in coin_pairs if search.upper() in c] if search else coin_pairs
        product_id = st.selectbox("SELECT CRYPTO PAIR", filtered_pairs, index=0 if filtered_pairs else None)
    
    # Timeframe strategico
    st.markdown("**STRATEGIC TIMEFRAME CONFIGURATION**")
    col1, col2 = st.columns(2)
    with col1:
        primary_tf = st.selectbox("PRIMARY TF", ["15m", "1H", "4H", "1D"], index=2)
    with col2:
        secondary_tf = st.selectbox("SECONDARY TF", ["1H", "4H", "1D", "1W"], index=1)
    
    # Risk management
    st.markdown("**RISK MANAGEMENT**")
    account_size = st.number_input("ACCOUNT SIZE ($)", min_value=100, value=5000, step=500)
    risk_percent = st.slider("RISK PER TRADE (%)", 0.5, 10.0, 2.0, step=0.5)
    risk_reward = st.selectbox("RISK/REWARD RATIO", ["1:1", "1:2", "1:3", "1:4"], index=2)
    
    # Strategia
    st.markdown("**TRADING STRATEGY**")
    strategy = st.selectbox("SELECT STRATEGY", ["Trend Following", "Breakout Trading", "Mean Reversion", "Ichimoku Cloud", "Finora AI Strategy"], index=4)
    
    st.markdown("---")
    run_analysis = st.button("🚀 RUN FINORA ANALYSIS", use_container_width=True, key="analyze")
    
    st.markdown("""
    <div style="text-align: center; margin-top: 1.5rem; font-size: 0.8rem; opacity: 0.7;">
        <p>Finora Pro Terminal v2.0</p>
        <p>© 2023 Finora Trading Technologies</p>
    </div>
    """, unsafe_allow_html=True)

# Funzioni avanzate per l'analisi
@st.cache_data(ttl=600, show_spinner=False)
def get_coinbase_ohlc(product_id, granularity, n_candles):
    """Ottiene i dati OHLC da Coinbase con caching"""
    url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"
    params = {"granularity": granularity, "limit": n_candles}
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        st.error(f"Coinbase API Error: {resp.status_code} - {resp.text}")
        return None
    
    data = resp.json()
    df = pd.DataFrame(data, columns=["time", "low", "high", "open", "close", "volume"])
    df = df.sort_values("time")
    df["Date"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("Date", inplace=True)
    df = df[["open", "high", "low", "close", "volume"]]
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    return df.astype(float)

def calculate_advanced_indicators(df):
    """Calcola tutti gli indicatori avanzati"""
    # Momentum Indicators
    df["RSI"] = RSIIndicator(df["Close"], window=14).rsi()
    df["Stoch_K"] = StochasticOscillator(df["High"], df["Low"], df["Close"], window=14).stoch()
    df["Stoch_D"] = StochasticOscillator(df["High"], df["Low"], df["Close"], window=14).stoch_signal()
    df["MACD"] = ta.trend.macd_diff(df["Close"])
    
    # Trend Indicators
    ichimoku = IchimokuIndicator(df["High"], df["Low"])
    df["Ichimoku_Base"] = ichimoku.ichimoku_base_line()
    df["Ichimoku_Conv"] = ichimoku.ichimoku_conversion_line()
    df["Ichimoku_A"] = ichimoku.ichimoku_a()
    df["Ichimoku_B"] = ichimoku.ichimoku_b()
    
    # Volatility Indicators
    bb = BollingerBands(df["Close"])
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Middle"] = bb.bollinger_mavg()
    df["BB_Lower"] = bb.bollinger_lband()
    
    # Other Indicators
    df["PSAR"] = PSARIndicator(df["High"], df["Low"], df["Close"]).psar()
    df["ADX"] = ta.trend.adx(df["High"], df["Low"], df["Close"], window=14)
    df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=14)
    
    return df.dropna()

def detect_key_levels(df, lookback=50):
    """Rileva livelli chiave con algoritmo avanzato"""
    # Supporti e resistenze con clustering
    prices = df[['High', 'Low']].tail(lookback).values.flatten()
    
    # Clustering per identificare livelli significativi
    bins = np.linspace(min(prices), max(prices), num=20)
    hist, bin_edges = np.histogram(prices, bins=bins)
    
    # Identifica i cluster significativi
    threshold = np.percentile(hist, 75)
    significant_bins = bin_edges[:-1][hist > threshold]
    
    # Identifica supporti e resistenze
    support_levels = []
    resistance_levels = []
    
    for i in range(1, len(significant_bins)):
        if hist[i] > hist[i-1] and hist[i] > hist[i+1]:
            resistance_levels.append(bin_edges[i])
        elif hist[i] < hist[i-1] and hist[i] < hist[i+1]:
            support_levels.append(bin_edges[i])
    
    # Prendi solo i livelli più significativi
    support_levels = sorted(support_levels)[:3]
    resistance_levels = sorted(resistance_levels)[-3:]
    
    # Swing high/low
    swing_high = df["High"].tail(lookback).max()
    swing_low = df["Low"].tail(lookback).min()
    
    # Fibonacci
    fib_levels = {
        "0.0": swing_high,
        "0.236": swing_high - 0.236 * (swing_high - swing_low),
        "0.382": swing_high - 0.382 * (swing_high - swing_low),
        "0.5": swing_high - 0.5 * (swing_high - swing_low),
        "0.618": swing_high - 0.618 * (swing_high - swing_low),
        "0.786": swing_high - 0.786 * (swing_high - swing_low),
        "1.0": swing_low
    }
    
    return support_levels, resistance_levels, swing_high, swing_low, fib_levels

def detect_fvg(df, lookback=30):
    """Rileva Fair Value Gaps con algoritmo avanzato"""
    fvg_zones = []
    df_sub = df.tail(lookback)
    
    for i in range(2, len(df_sub)):
        current = df_sub.iloc[i]
        prev = df_sub.iloc[i-1]
        prev2 = df_sub.iloc[i-2]
        
        # Bullish FVG (demand)
        if current["Low"] > prev2["High"]:
            fvg_zones.append({
                "start": df_sub.index[i-2],
                "end": df_sub.index[i],
                "type": "DEMAND",
                "y0": prev2["High"],
                "y1": current["Low"]
            })
        
        # Bearish FVG (supply)
        if current["High"] < prev2["Low"]:
            fvg_zones.append({
                "start": df_sub.index[i-2],
                "end": df_sub.index[i],
                "type": "SUPPLY",
                "y0": prev2["Low"],
                "y1": current["High"]
            })
    
    return fvg_zones

def generate_price_chart(df, support_levels, resistance_levels, swing_high, swing_low, fib_levels, fvg_zones):
    """Genera il grafico avanzato con tutti gli indicatori"""
    fig = go.Figure()
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ))
    
    # Ichimoku Cloud
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['Ichimoku_A'],
        line=dict(color='#3498db', width=1),
        name='Ichimoku A'
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['Ichimoku_B'],
        line=dict(color='#e74c3c', width=1),
        name='Ichimoku B',
        fill='tonexty',
        fillcolor='rgba(231, 76, 60, 0.1)'
    ))
    
    # Bollinger Bands
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['BB_Upper'],
        line=dict(color='#9b59b6', width=1),
        name='BB Upper'
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['BB_Middle'],
        line=dict(color='#34495e', width=1),
        name='BB Middle'
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['BB_Lower'],
        line=dict(color='#2ecc71', width=1),
        name='BB Lower'
    ))
    
    # Support Levels
    for level in support_levels:
        fig.add_hline(y=level, line_dash="dash", line_color="green", 
                     annotation_text=f"Support: {level:.2f}", 
                     annotation_position="bottom right")
    
    # Resistance Levels
    for level in resistance_levels:
        fig.add_hline(y=level, line_dash="dash", line_color="red", 
                     annotation_text=f"Resistance: {level:.2f}", 
                     annotation_position="top right")
    
    # Swing Levels
    fig.add_hline(y=swing_high, line_dash="dot", line_color="blue", 
                 annotation_text=f"Swing High: {swing_high:.2f}")
    fig.add_hline(y=swing_low, line_dash="dot", line_color="blue", 
                 annotation_text=f"Swing Low: {swing_low:.2f}")
    
    # Fibonacci Levels
    color_map = {
        "0.0": "purple", "0.236": "blue", "0.382": "teal", "0.5": "orange",
        "0.618": "green", "0.786": "red", "1.0": "black"
    }
    for k, v in fib_levels.items():
        fig.add_hline(y=v, line_dash="dot", line_color=color_map.get(k, "gray"), 
                     annotation_text=f"Fib {k}")
    
    # FVG Zones
    for zone in fvg_zones:
        color = "rgba(50, 200, 100, 0.2)" if zone["type"] == "DEMAND" else "rgba(255, 80, 80, 0.2)"
        fig.add_vrect(
            x0=zone["start"], x1=zone["end"],
            y0=zone["y0"], y1=zone["y1"],
            fillcolor=color, line_width=0,
            annotation_text=zone["type"]
        )
    
    fig.update_layout(
        title=f"{product_id} Price Analysis ({primary_tf})",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        template="plotly_dark",
        hovermode="x unified",
        showlegend=True,
        height=600
    )
    
    return fig

def generate_trading_signals(df, support_levels, resistance_levels, swing_high, swing_low):
    """Genera segnali di trading avanzati"""
    last = df.iloc[-1]
    signals = []
    
    # Bullish signals
    if last["Close"] > last["Ichimoku_A"] and last["Close"] > last["Ichimoku_B"]:
        signals.append("Ichimoku Cloud Bullish")
    
    if last["Close"] > last["BB_Middle"] and last["Close"] < last["BB_Upper"]:
        signals.append("Price in Upper Bollinger Band")
    
    if last["RSI"] > 50 and last["RSI"] < 70:
        signals.append("RSI Bullish (50-70)")
    
    # Bearish signals
    if last["Close"] < last["Ichimoku_A"] and last["Close"] < last["Ichimoku_B"]:
        signals.append("Ichimoku Cloud Bearish")
    
    if last["Close"] < last["BB_Middle"] and last["Close"] > last["BB_Lower"]:
        signals.append("Price in Lower Bollinger Band")
    
    if last["RSI"] < 50 and last["RSI"] > 30:
        signals.append("RSI Bearish (30-50)")
    
    # Key level signals
    for level in support_levels:
        if abs(last["Close"] - level) < (swing_high - swing_low) * 0.02:
            signals.append(f"Near Support: {level:.2f}")
    
    for level in resistance_levels:
        if abs(last["Close"] - level) < (swing_high - swing_low) * 0.02:
            signals.append(f"Near Resistance: {level:.2f}")
    
    return signals

def generate_trade_scenarios(df, support_levels, resistance_levels, swing_high, swing_low, atr):
    """Genera scenari di trading professionali"""
    last = df.iloc[-1]
    scenarios = []
    
    # Bullish scenario
    if last["Close"] > last["Ichimoku_A"] and last["Close"] > last["BB_Middle"]:
        entry = last["Close"] - atr * 0.5
        stop_loss = last["Close"] - atr * 1.5
        take_profit = last["Close"] + atr * 3
        
        scenario = {
            "type": "BUY",
            "confidence": "High" if last["Volume"] > df["Volume"].mean() else "Medium",
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": "Bullish trend confirmed by Ichimoku Cloud and Bollinger Bands",
            "levels": f"Support: {min(support_levels):.2f}, Resistance: {max(resistance_levels):.2f}"
        }
        scenarios.append(scenario)
    
    # Bearish scenario
    if last["Close"] < last["Ichimoku_A"] and last["Close"] < last["BB_Middle"]:
        entry = last["Close"] + atr * 0.5
        stop_loss = last["Close"] + atr * 1.5
        take_profit = last["Close"] - atr * 3
        
        scenario = {
            "type": "SELL",
            "confidence": "High" if last["Volume"] > df["Volume"].mean() else "Medium",
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": "Bearish trend confirmed by Ichimoku Cloud and Bollinger Bands",
            "levels": f"Support: {min(support_levels):.2f}, Resistance: {max(resistance_levels):.2f}"
        }
        scenarios.append(scenario)
    
    return scenarios

# ================= MAIN APP =================
if run_analysis:
    # Mappa dei timeframe
    tf_map = {
        "15m": 900,
        "1H": 3600,
        "4H": 14400,
        "1D": 86400
    }
    
    with st.spinner("🔍 Running advanced market analysis..."):
        # Ottieni dati
        df = get_coinbase_ohlc(product_id, tf_map[primary_tf], 200)
        
        if df is None or len(df) < 50:
            st.error("Insufficient data for analysis. Please try a different pair or timeframe.")
            st.stop()
        
        # Calcola indicatori avanzati
        df = calculate_advanced_indicators(df)
        
        # Rileva livelli chiave
        support_levels, resistance_levels, swing_high, swing_low, fib_levels = detect_key_levels(df)
        
        # Rileva FVG
        fvg_zones = detect_fvg(df)
        
        # Genera segnali
        signals = generate_trading_signals(df, support_levels, resistance_levels, swing_high, swing_low)
        
        # Genera scenari di trading
        atr = df["ATR"].iloc[-1]
        trade_scenarios = generate_trade_scenarios(df, support_levels, resistance_levels, swing_high, swing_low, atr)
        
        # Prezzo corrente
        current_price = df["Close"].iloc[-1]
        price_change = ((current_price - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
        
        # Mostra risultati
        st.success("Analysis Complete!")
        
        # Market Overview
        st.markdown("""
        <div class="card">
            <h2 style="margin-top: 0;">📊 Market Overview</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                <div class="indicator-box">
                    <div>{}</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${:.2f}</div>
                    <div class="{}">{:.2f}%</div>
                </div>
                <div class="indicator-box">
                    <div>Market Trend</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">{}</div>
                    <div>ADX: {:.1f}</div>
                </div>
                <div class="indicator-box">
                    <div>Volatility (ATR)</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${:.2f}</div>
                    <div>{:.1f}% of price</div>
                </div>
                <div class="indicator-box">
                    <div>Volume (24h)</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">{:.0f}</div>
                    <div>{}</div>
                </div>
            </div>
        </div>
        """.format(
            product_id,
            current_price,
            "positive" if price_change > 0 else "negative",
            price_change,
            "Bullish" if df["Close"].iloc[-1] > df["Close"].iloc[-20] else "Bearish",
            df["ADX"].iloc[-1],
            atr,
            (atr / current_price) * 100,
            df["Volume"].mean(),
            "Above average" if df["Volume"].iloc[-1] > df["Volume"].mean() else "Below average"
        ), unsafe_allow_html=True)
        
        # Trading Signals
        st.markdown("""
        <div class="card">
            <h2 style="margin-top: 0;">🚦 Trading Signals</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem;">
        """, unsafe_allow_html=True)
        
        for signal in signals:
            signal_type = "positive" if "Bullish" in signal or "Support" in signal else "negative"
            st.markdown(f"""
            <div class="indicator-box">
                <div style="display: flex; justify-content: space-between;">
                    <div>{signal}</div>
                    <div class="{signal_type}">●</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)
        
        # Trade Scenarios
        if trade_scenarios:
            for scenario in trade_scenarios:
                scenario_class = "signal-buy" if scenario["type"] == "BUY" else "signal-sell"
                st.markdown(f"""
                <div class="signal-card {scenario_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h3 style="margin: 0;">{scenario['type']} SIGNAL - Confidence: {scenario['confidence']}</h3>
                        <span style="background: {'#27ae60' if scenario['type'] == 'BUY' else '#e74c3c'}; 
                                color: white; padding: 5px 15px; border-radius: 20px;">
                            {scenario['type']}
                        </span>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1.5rem;">
                        <div>
                            <div style="font-size: 0.9rem;">Entry Point</div>
                            <div style="font-size: 1.5rem; font-weight: 700;">${scenario['entry']:.2f}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.9rem;">Take Profit</div>
                            <div style="font-size: 1.5rem; font-weight: 700; color: #27ae60;">${scenario['take_profit']:.2f}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.9rem;">Stop Loss</div>
                            <div style="font-size: 1.5rem; font-weight: 700; color: #e74c3c;">${scenario['stop_loss']:.2f}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.9rem;">Risk/Reward</div>
                            <div style="font-size: 1.5rem; font-weight: 700;">1:{abs((scenario['take_profit']-scenario['entry'])/(scenario['entry']-scenario['stop_loss']):.1f}</div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 1rem;">
                        <div style="font-weight: 600;">Rationale:</div>
                        <div>{scenario['reason']}</div>
                    </div>
                    
                    <div style="margin-top: 1rem;">
                        <div style="font-weight: 600;">Key Levels:</div>
                        <div>{scenario['levels']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="card">
                <div style="text-align: center; padding: 2rem;">
                    <h3>No Strong Trading Signals Detected</h3>
                    <p>Market is in consolidation phase. Wait for clearer signals.</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Price Chart
        st.markdown("""
        <div class="card">
            <h2 style="margin-top: 0;">📈 Advanced Price Analysis</h2>
        """, unsafe_allow_html=True)
        
        fig = generate_price_chart(df, support_levels, resistance_levels, swing_high, swing_low, fib_levels, fvg_zones)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Risk Management
        st.markdown("""
        <div class="card">
            <h2 style="margin-top: 0;">🛡️ Risk Management</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                <div class="indicator-box">
                    <div>Max Risk per Trade</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">${account_size * risk_percent/100:.2f}</div>
                    <div>({risk_percent}% of ${account_size:.0f})</div>
                </div>
                <div class="indicator-box">
                    <div>Position Size</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">{account_size * risk_percent/100 / atr:.2f} {product_id.split('-')[0]}</div>
                    <div>Based on ATR</div>
                </div>
                <div class="indicator-box">
                    <div>Risk/Reward Ratio</div>
                    <div style="font-size: 1.8rem; font-weight: 700;">{risk_reward}</div>
                    <div>Minimum target</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Disclaimer
        st.markdown("""
        <div class="card" style="background: rgba(231, 76, 60, 0.1); border-left: 4px solid #e74c3c;">
            <div style="display: flex; gap: 12px;">
                <div style="color: #e74c3c; font-size: 2rem;">⚠️</div>
                <div>
                    <h3 style="margin-top: 0; color: #e74c3c;">RISK DISCLAIMER</h3>
                    <p>Trading involves significant risk of loss. The analysis provided by Finora Pro Terminal is for informational purposes only and should not be considered financial advice. Past performance is not indicative of future results. Always conduct your own research and consider consulting with a qualified financial advisor before making any trading decisions.</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    # Schermata iniziale
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="card">
            <h2 style="margin-top: 0;">Welcome to Finora Pro Terminal</h2>
            <p>Advanced trading analysis for crypto, forex, and stocks.</p>
            
            <div style="margin: 2rem 0;">
                <h3>🚀 Key Features:</h3>
                <ul>
                    <li>Multi-timeframe market analysis</li>
                    <li>Professional trading signals</li>
                    <li>Institutional-grade charting</li>
                    <li>Advanced risk management tools</li>
                    <li>Real-time market scanning</li>
                    <li>Automated trade scenarios</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 2rem;">
                <p>Configure your analysis parameters in the sidebar and click "RUN FINORA ANALYSIS" to begin.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="card">
            <div style="text-align: center;">
                <svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#3498db" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                    <line x1="12" y1="22.08" x2="12" y2="12"></line>
                </svg>
                <h3>Connect to Finora Ecosystem</h3>
                <p>Enhance your trading with our integrated tools:</p>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1.5rem;">
                    <div class="indicator-box">
                        <div>Telegram Bot</div>
                        <div style="font-size: 0.9rem; margin-top: 0.5rem;">Real-time alerts</div>
                    </div>
                    <div class="indicator-box">
                        <div>Mobile App</div>
                        <div style="font-size: 0.9rem; margin-top: 0.5rem;">Trade on the go</div>
                    </div>
                    <div class="indicator-box">
                        <div>API Access</div>
                        <div style="font-size: 0.9rem; margin-top: 0.5rem;">Automate strategies</div>
                    </div>
                    <div class="indicator-box">
                        <div>Premium Signals</div>
                        <div style="font-size: 0.9rem; margin-top: 0.5rem;">Institutional grade</div>
                    </div>
                </div>
                
                <div style="margin-top: 2rem;">
                    <a href="https://t.me/FinoraEN_Bot" target="_blank">
                        <button style="background: linear-gradient(90deg, #2e86de, #3498db); 
                                    border: none; color: white; padding: 0.8rem 1.5rem; 
                                    border-radius: 12px; font-weight: 600; cursor: pointer;
                                    width: 100%;">
                            Connect to Telegram Bot
                        </button>
                    </a>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
