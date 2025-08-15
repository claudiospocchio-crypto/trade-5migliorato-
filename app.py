import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
from ta.trend import PSARIndicator
import plotly.graph_objs as go

st.set_page_config("Coinbase Advanced Crypto Analysis", layout="wide")
st.title("🤖 Coinbase Crypto Advanced Report")

# Scarica la lista delle coppie disponibili da Coinbase
@st.cache_data(ttl=3600)
def get_coinbase_products():
    url = "https://api.exchange.coinbase.com/products"
    resp = requests.get(url)
    data = resp.json()
    pairs = [p["id"] for p in data if p["quote_currency"] == "USD" and p["trading_disabled"] is False]
    return sorted(pairs)

coin_pairs = get_coinbase_products()
search = st.text_input("Cerca simbolo crypto (es: BTC, ETH, SHIB...)", "")
filtered_pairs = [c for c in coin_pairs if search.upper() in c] if search else coin_pairs
if not filtered_pairs:
    st.warning("Nessuna crypto trovata per la ricerca inserita.")
product_id = st.selectbox("Scegli coppia Coinbase", filtered_pairs, index=0 if filtered_pairs else None)

_tf_map = {
    "1 minuto": 60,
    "5 minuti": 300,
    "15 minuti": 900,
    "1 ora": 3600,
    "6 ore": 21600,
    "1 giorno": 86400
}
tf_label = st.selectbox("Timeframe", list(_tf_map.keys()), index=2)
granularity = _tf_map[tf_label]

n_candles = st.slider("Quante candele di storico?", min_value=30, max_value=300, value=120)

def get_coinbase_ohlc(product_id, granularity, n_candles):
    url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"
    params = {"granularity": granularity, "limit": n_candles}
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        raise Exception(f"Errore Coinbase API: {resp.text}")
    data = resp.json()
    df = pd.DataFrame(data, columns=["time", "low", "high", "open", "close", "volume"])
    df = df.sort_values("time")
    df["Date"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("Date", inplace=True)
    df = df[["open", "high", "low", "close", "volume"]]
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    df = df.astype(float)
    return df

def get_fibonacci_levels(df, lookback=30):
    highest = df["High"][-lookback:].max()
    lowest = df["Low"][-lookback:].min()
    diff = highest - lowest
    levels = {
        "0%": highest,
        "23.6%": highest - 0.236 * diff,
        "38.2%": highest - 0.382 * diff,
        "50%": highest - 0.5 * diff,
        "61.8%": highest - 0.618 * diff,
        "78.6%": highest - 0.786 * diff,
        "100%": lowest
    }
    return levels

def find_fvg(df):
    # Lista di tuple (inizio, fine, tipo) dove tipo=SUPPLY/DEMAND
    fvg_zones = []
    for i in range(2, len(df)):
        # FVG Bullish (DEMAND): min corrente > max due barre fa
        if df["Low"].iloc[i] > df["High"].iloc[i - 2]:
            fvg_zones.append((df.index[i-2], df.index[i], "DEMAND", df["High"].iloc[i-2], df["Low"].iloc[i]))
        # FVG Bearish (SUPPLY): max corrente < min due barre fa
        if df["High"].iloc[i] < df["Low"].iloc[i - 2]:
            fvg_zones.append((df.index[i-2], df.index[i], "SUPPLY", df["Low"].iloc[i-2], df["High"].iloc[i]))
    return fvg_zones

if st.button("Scarica e analizza"):
    with st.spinner("Scarico dati da Coinbase..."):
        try:
            df = get_coinbase_ohlc(product_id, granularity, n_candles)
        except Exception as e:
            st.error(str(e))
            df = None

    if df is not None and len(df) > 20:
        # Indicatori
        df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
        df["MFI"] = ta.volume.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], window=14)
        df["ADX"] = ta.trend.adx(df["High"], df["Low"], df["Close"], window=14)
        df["+DI"] = ta.trend.adx_pos(df["High"], df["Low"], df["Close"], window=14)
        df["-DI"] = ta.trend.adx_neg(df["High"], df["Low"], df["Close"], window=14)
        psar = PSARIndicator(high=df["High"], low=df["Low"], close=df["Close"])
        df["PSAR"] = psar.psar()
        df["Momentum"] = ta.momentum.roc(df["Close"], window=10)
        df["MACD"] = ta.trend.macd(df["Close"])
        df["MACD_signal"] = ta.trend.macd_signal(df["Close"])
        df = df.dropna()

        # Swing high/low
        lookback = 30
        swing_high = df["High"][-lookback:].max()
        swing_low = df["Low"][-lookback:].min()
        equilibrio = (swing_high + swing_low) / 2

        # Fibonacci
        fib_levels = get_fibonacci_levels(df, lookback=lookback)

        # FVG supply and demand
        fvg_zones = find_fvg(df[-lookback:])

        # Volumi
        vol_media = df["Volume"][-lookback:].mean()
        spike = df["Volume"].iloc[-1] > 2 * vol_media

        # Manipolazione
        liquidity_grab_up = (df["High"].iloc[-1] > swing_high) and (df["Close"].iloc[-1] < swing_high)
        liquidity_grab_down = (df["Low"].iloc[-1] < swing_low) and (df["Close"].iloc[-1] > swing_low)

        liquidity_text = ""
        if liquidity_grab_up:
            liquidity_text += "- **Presa di liquidità sopra il massimo recente** (possibile manipolazione rialzista)\n"
        if liquidity_grab_down:
            liquidity_text += "- **Presa di liquidità sotto il minimo recente** (possibile manipolazione ribassista)\n"
        if spike:
            liquidity_text += "- **Volume anomalo rilevato nell’ultima candela**\n"
        if not liquidity_text:
            liquidity_text = "- Nessuna manipolazione/volume anomalo rilevato."

        # Trend e segnali
        last = df.iloc[-1]
        last_prev = df.iloc[-2]
        bull_conds = [
            last["MACD"] > last["MACD_signal"],
            last["RSI"] > 55,
            last["ADX"] > 20 and last["+DI"] > last["-DI"],
            last["MFI"] < 60,
            last["PSAR"] < last["Close"],
            last["Momentum"] > last_prev["Momentum"]
        ]
        bear_conds = [
            last["MACD"] < last["MACD_signal"],
            last["RSI"] < 45,
            last["ADX"] > 20 and last["+DI"] < last["-DI"],
            last["MFI"] > 40,
            last["PSAR"] > last["Close"],
            last["Momentum"] < last_prev["Momentum"]
        ]
        if sum(bull_conds) >= 4:
            trend = "📈 Rialzista"
            signal = "🟢 **Acquisto** (BUY)"
        elif sum(bear_conds) >= 4:
            trend = "📉 Ribassista"
            signal = "🔴 **Vendita** (SELL)"
        else:
            trend = "🔄 Laterale/Equilibrio"
            signal = "🟡 **Attendere** (wait)"

        last_close = last["Close"]
        if "BUY" in signal:
            take_profit = last_close * 1.03
            stop_loss = last_close * 0.98
        elif "SELL" in signal:
            take_profit = last_close * 0.97
            stop_loss = last_close * 1.02
        else:
            take_profit = np.nan
            stop_loss = np.nan

        # Report
        report = f"""
🔍 **Valutazione Generale:**

- Il prezzo attuale di **{product_id}** è **{last_close:.4f} USD**
- Timeframe: **{tf_label}**
- Trend di fondo: **{trend}**
- Segnale operativo: {signal}

📈 **Livelli critici osservati:**
- Swing High: {swing_high:.4f}
- Swing Low: {swing_low:.4f}
- Equilibrio: {equilibrio:.4f}
- Fibonacci: """ + " | ".join([f"{k}: {v:.2f}" for k, v in fib_levels.items()]) + """

---
**Zone di inversione & manipolazione:**
""" + liquidity_text + """

---
**Zone FVG supply/demand (ultime 30 barre):**
""" + ("\n".join([
    f"- {zona}: da {df.index.get_loc(start)} a {df.index.get_loc(end)}, prezzi {p1:.2f}→{p2:.2f}"
    for start, end, zona, p1, p2 in fvg_zones
]) if fvg_zones else "- Nessuna FVG rilevata") + """

---
**Indicatori chiave:**
- RSI: {rsi:.2f}
- Momentum: {mom:.2f}
- PSAR: {psar:.4f}
- ADX: {adx:.2f}
- MFI: {mfi:.2f}
- MACD: {macd:.4f} / {macdsig:.4f}
""".format(
    rsi=last["RSI"], mom=last["Momentum"], psar=last["PSAR"], adx=last["ADX"],
    mfi=last["MFI"], macd=last["MACD"], macdsig=last["MACD_signal"]
)
        st.info(report)

        st.subheader("📊 Grafico prezzi, Fibonacci, FVG e volumi")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"
        ))
        # Fibonacci levels
        color_map = {
            "0%": "purple", "23.6%": "blue", "38.2%": "teal", "50%": "orange",
            "61.8%": "green", "78.6%": "red", "100%": "black"
        }
        for k, v in fib_levels.items():
            fig.add_hline(y=v, line_dash="dot", line_color=color_map.get(k, "gray"), annotation_text=f"Fib {k}")

        # FVG supply/demand
        for start, end, zona, p1, p2 in fvg_zones:
            color = "rgba(50,200,100,0.2)" if zona == "DEMAND" else "rgba(255,80,80,0.2)"
            fig.add_vrect(x0=start, x1=end, y0=p1, y1=p2, fillcolor=color, line_width=0, annotation_text=zona)

        # TP/SL
        if not np.isnan(take_profit):
            fig.add_hline(y=take_profit, line=dict(color="green", dash="dash"), annotation_text="Take Profit")
        if not np.isnan(stop_loss):
            fig.add_hline(y=stop_loss, line=dict(color="red", dash="dash"), annotation_text="Stop Loss")
        st.plotly_chart(fig, use_container_width=True)

        # Volumi
        st.subheader("📈 Volumi e dati indicatori")
        st.line_chart(df["Volume"])
        st.dataframe(df.tail(20))

    else:
        st.warning("Dati insufficienti o errore nel download.")
else:
    st.info("Cerca la crypto, seleziona timeframe e premi Scarica e analizza.")

st.caption("⚠️ Questo report è generato automaticamente dall’AI e NON è un consiglio finanziario. Verifica sempre dati e strategia.")
