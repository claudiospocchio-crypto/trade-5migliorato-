import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
from ta.trend import PSARIndicator

st.set_page_config("Coinbase Crypto Analysis", layout="wide")
st.title("🤖 Coinbase Crypto Report (multi-timeframe)")

# Scarica la lista delle coppie disponibili da Coinbase
@st.cache_data(ttl=3600)
def get_coinbase_products():
    url = "https://api.exchange.coinbase.com/products"
    resp = requests.get(url)
    data = resp.json()
    # Prendi solo le coppie contro USD
    pairs = [p["id"] for p in data if p["quote_currency"] == "USD" and p["trading_disabled"] is False]
    return sorted(pairs)

coin_pairs = get_coinbase_products()
search = st.text_input("Cerca simbolo crypto (es: BTC, ETH, SHIB...)", "")
if search:
    filtered_pairs = [c for c in coin_pairs if search.upper() in c]
else:
    filtered_pairs = coin_pairs
if not filtered_pairs:
    st.warning("Nessuna crypto trovata per la ricerca inserita.")
product_id = st.selectbox("Scegli coppia Coinbase", filtered_pairs, index=0 if filtered_pairs else None)

# SOLO granularità supportate da Coinbase
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
    params = {
        "granularity": granularity,
        "limit": n_candles
    }
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
        # PSAR
        psar = PSARIndicator(high=df["High"], low=df["Low"], close=df["Close"])
        df["PSAR"] = psar.psar()
        df["Momentum"] = ta.momentum.roc(df["Close"], window=10)
        df["MACD"] = ta.trend.macd(df["Close"])
        df["MACD_signal"] = ta.trend.macd_signal(df["Close"])
        df = df.dropna()

        # Individua swing high/low e zone di inversione
        lookback = 30
        swing_high = df["High"][-lookback:].max()
        swing_low = df["Low"][-lookback:].min()
        equilibrio = (swing_high + swing_low) / 2

        # Individua prese di liquidità/manipolazione
        liquidity_grab_up = (
            (df["High"].iloc[-1] > swing_high) and
            (df["Close"].iloc[-1] < swing_high)
        )
        liquidity_grab_down = (
            (df["Low"].iloc[-1] < swing_low) and
            (df["Close"].iloc[-1] > swing_low)
        )

        # Spike di volume
        vol_media = df["Volume"][-lookback:].mean()
        spike = df["Volume"].iloc[-1] > 2 * vol_media

        # Testi zone manipolazione/inversione
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

        # Take Profit e Stop Loss
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

        # Livelli swing per il report
        last_high = swing_high
        last_low = swing_low
        last_eq = equilibrio

        # Report
        report = f"""
🔍 **Valutazione Generale:**

- Il prezzo attuale di **{product_id}** è **{last_close:.4f} USD**
- Timeframe: **{tf_label}**
- Il trend di fondo è: **{trend}**
- La maggior parte degli indicatori principali (MACD, Momentum, RSI, PSAR, ADX, MFI) sono orientati a {'rialzo' if sum(bull_conds) >= 4 else 'ribasso' if sum(bear_conds) >= 4 else 'equilibrio'}.
- Attuale segnale operativo: {signal}

📈 **Livelli critici osservati:**
- Massimo swing recente: {last_high:.4f}
- Minimo swing recente: {last_low:.4f}
- Area di equilibrio: {last_eq:.4f}

🎯 **Strategia consigliata:**  
"""
        if "BUY" in signal:
            report += f"- Compra ora, Take Profit a {take_profit:.4f}, Stop Loss a {stop_loss:.4f}\n"
        elif "SELL" in signal:
            report += f"- Vendi ora, Take Profit a {take_profit:.4f}, Stop Loss a {stop_loss:.4f}\n"
        else:
            report += "- Attendere: non ci sono condizioni forti per entrare ora.\n"

        # Extra dettagli indicatori
        report += f"""
---
**Indicatori chiave:**
- RSI: {last['RSI']:.2f}
- Momentum: {last['Momentum']:.2f}
- PSAR: {last['PSAR']:.4f}
- ADX: {last['ADX']:.2f}
- MFI: {last['MFI']:.2f}
- MACD: {last['MACD']:.4f} / {last['MACD_signal']:.4f}
"""

        # Zone inversione/manipolazione/volumi
        report += f"""\n
🔍 **Zone di inversione & manipolazione:**
{liquidity_text}
"""

        st.info(report)

        st.subheader("📊 Grafico prezzi, swing, inversioni e volumi anomali")
        import plotly.graph_objs as go
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"
        ))
        # Swing levels
        fig.add_hline(y=last_high, line_dash="dot", annotation_text="Swing High", opacity=0.6)
        fig.add_hline(y=last_low, line_dash="dot", annotation_text="Swing Low", opacity=0.6)
        fig.add_hline(y=last_eq, line_dash="dot", annotation_text="Equilibrio", opacity=0.5)
        # TP/SL
        if not np.isnan(take_profit):
            fig.add_hline(y=take_profit, line=dict(color="green", dash="dash"), annotation_text="Take Profit")
        if not np.isnan(stop_loss):
            fig.add_hline(y=stop_loss, line=dict(color="red", dash="dash"), annotation_text="Stop Loss")
        # Marker per manipolazione/volume spike
        shapes = []
        if liquidity_grab_up:
            shapes.append(dict(type="circle", xref="x", yref="y",
                              x0=df.index[-1], x1=df.index[-1], y0=df["High"].iloc[-1], y1=df["High"].iloc[-1]+(last_high*0.01),
                              line_color="blue", fillcolor="blue"))
        if liquidity_grab_down:
            shapes.append(dict(type="circle", xref="x", yref="y",
                              x0=df.index[-1], x1=df.index[-1], y0=df["Low"].iloc[-1]-last_low*0.01, y1=df["Low"].iloc[-1],
                              line_color="orange", fillcolor="orange"))
        if spike:
            shapes.append(dict(type="circle", xref="x", yref="y",
                              x0=df.index[-1], x1=df.index[-1], y0=last_close, y1=last_close + last_close*0.01,
                              line_color="red", fillcolor="red"))
        fig.update_layout(shapes=shapes)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Ultimi dati & indicatori")
        st.dataframe(df.tail(20))

    else:
        st.warning("Dati insufficienti o errore nel download.")
else:
    st.info("Cerca la crypto, seleziona timeframe e premi Scarica e analizza.")

st.caption("⚠️ Questo report è generato automaticamente dall’AI e NON è un consiglio finanziario. Verifica sempre dati e strategia.")
