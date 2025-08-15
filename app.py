import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
from ta.trend import PSARIndicator
import plotly.graph_objs as go

st.set_page_config("Coinbase Advanced Crypto Analysis", layout="wide")
st.title("🤖 Coinbase Crypto Advanced Report")

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
    "30 minuti": 1800,
    "1 ora": 3600,
    "2 ore": 7200,
    "4 ore": 14400,
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
    fvg_zones = []
    for i in range(2, len(df)):
        # FVG Bullish (DEMAND): min corrente > max due barre fa
        if df["Low"].iloc[i] > df["High"].iloc[i - 2]:
            fvg_zones.append({
                "start": df.index[i-2],
                "end": df.index[i],
                "type": "DEMAND",
                "y0": df["High"].iloc[i-2],
                "y1": df["Low"].iloc[i]
            })
        # FVG Bearish (SUPPLY): max corrente < min due barre fa
        if df["High"].iloc[i] < df["Low"].iloc[i - 2]:
            fvg_zones.append({
                "start": df.index[i-2],
                "end": df.index[i],
                "type": "SUPPLY",
                "y0": df["Low"].iloc[i-2],
                "y1": df["High"].iloc[i]
            })
    return fvg_zones

def suggest_entry_tp_sl(df, fvg_zones):
    last_close = df["Close"].iloc[-1]
    candidates = []
    for zona in fvg_zones[-10:]:
        if zona["type"] == "DEMAND" and (zona["y0"] <= last_close <= zona["y1"] or zona["y1"] <= last_close <= zona["y0"]):
            direction = "LONG"
            entry = min(zona["y0"], zona["y1"])
            sl = entry - abs(zona["y1"]-zona["y0"])
            tp = entry + 2 * abs(zona["y1"]-zona["y0"])
            candidates.append({"zona": zona, "direction": direction, "entry": entry, "tp": tp, "sl": sl})
        elif zona["type"] == "SUPPLY" and (zona["y0"] >= last_close >= zona["y1"] or zona["y1"] >= last_close >= zona["y0"]):
            direction = "SHORT"
            entry = max(zona["y0"], zona["y1"])
            sl = entry + abs(zona["y1"]-zona["y0"])
            tp = entry - 2 * abs(zona["y1"]-zona["y0"])
            candidates.append({"zona": zona, "direction": direction, "entry": entry, "tp": tp, "sl": sl})
    if not candidates and fvg_zones:
        fvg = min(fvg_zones, key=lambda z: min(abs(df["Close"].iloc[-1] - z["y0"]), abs(df["Close"].iloc[-1] - z["y1"])))
        if fvg["type"] == "DEMAND":
            direction = "LONG"
            entry = min(fvg["y0"], fvg["y1"])
            sl = entry - abs(fvg["y1"]-fvg["y0"])
            tp = entry + 2 * abs(fvg["y1"]-fvg["y0"])
        else:
            direction = "SHORT"
            entry = max(fvg["y0"], fvg["y1"])
            sl = entry + abs(fvg["y1"]-fvg["y0"])
            tp = entry - 2 * abs(fvg["y1"]-fvg["y0"])
        return {"zona": fvg, "direction": direction, "entry": entry, "tp": tp, "sl": sl}
    return candidates[0] if candidates else None

if st.button("Scarica e analizza"):
    with st.spinner("Scarico dati da Coinbase..."):
        try:
            df = get_coinbase_ohlc(product_id, granularity, n_candles)
        except Exception as e:
            st.error(str(e))
            df = None

    if df is not None and len(df) > 20:
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

        lookback = 30
        swing_high = df["High"][-lookback:].max()
        swing_low = df["Low"][-lookback:].min()
        equilibrio = (swing_high + swing_low) / 2

        fib_levels = get_fibonacci_levels(df, lookback=lookback)
        fvg_zones = find_fvg(df[-lookback:])
        entry_plan = suggest_entry_tp_sl(df, fvg_zones)

        vol_media = df["Volume"][-lookback:].mean()
        spike = df["Volume"].iloc[-1] > 2 * vol_media

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

        if entry_plan:
            fvg_descr = f"Zona FVG {'DEMAND' if entry_plan['direction']=='LONG' else 'SUPPLY'}"
            fvg_descr += f" ({entry_plan['zona']['start'].strftime('%Y-%m-%d %H:%M')} → {entry_plan['zona']['end'].strftime('%Y-%m-%d %H:%M')})"
            fvg_descr += f"\n- **{entry_plan['direction']} ENTRY**: {entry_plan['entry']:.2f}\n- **Take Profit**: {entry_plan['tp']:.2f}\n- **Stop Loss**: {entry_plan['sl']:.2f}"
        else:
            fvg_descr = "Nessuna zona FVG vicina/attiva per un ingresso immediato."

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
**Operatività FVG supply/demand:**

""" + fvg_descr + """

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
        color_map = {
            "0%": "purple", "23.6%": "blue", "38.2%": "teal", "50%": "orange",
            "61.8%": "green", "78.6%": "red", "100%": "black"
        }
        for k, v in fib_levels.items():
            fig.add_hline(y=v, line_dash="dot", line_color=color_map.get(k, "gray"), annotation_text=f"Fib {k}")

        for zona in fvg_zones:
            color = "rgba(50,200,100,0.2)" if zona["type"] == "DEMAND" else "rgba(255,80,80,0.2)"
            fig.add_vrect(x0=zona["start"], x1=zona["end"], y0=zona["y0"], y1=zona["y1"], fillcolor=color, line_width=0, annotation_text=zona["type"])

        if entry_plan:
            fig.add_hline(y=entry_plan["entry"], line=dict(color="blue", width=2), annotation_text="Entry FVG")
            fig.add_hline(y=entry_plan["tp"], line=dict(color="green", dash="dash"), annotation_text="TP FVG")
            fig.add_hline(y=entry_plan["sl"], line=dict(color="red", dash="dash"), annotation_text="SL FVG")

        if not np.isnan(take_profit):
            fig.add_hline(y=take_profit, line=dict(color="green", dash="dot"), annotation_text="Take Profit")
        if not np.isnan(stop_loss):
            fig.add_hline(y=stop_loss, line=dict(color="red", dash="dot"), annotation_text="Stop Loss")

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Volumi e ultimi dati")
        st.line_chart(df["Volume"])
        st.dataframe(df.tail(20))

    else:
        st.warning("Dati insufficienti o errore nel download.")
else:
    st.info("Cerca la crypto, seleziona timeframe e premi Scarica e analizza.")

st.caption("⚠️ Questo report è generato automaticamente dall’AI e NON è un consiglio finanziario. Verifica sempre dati e strategia.")
