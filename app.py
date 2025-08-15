import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
from ta.trend import PSARIndicator
import plotly.graph_objs as go

st.set_page_config("Coinbase Crypto Advanced Report", layout="wide")
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

# SOLO granularità realmente supportate da Coinbase!
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
            rr = (tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else np.nan
            candidates.append({"zona": zona, "direction": direction, "entry": entry, "tp": tp, "sl": sl, "rr": rr})
        elif zona["type"] == "SUPPLY" and (zona["y0"] >= last_close >= zona["y1"] or zona["y1"] >= last_close >= zona["y0"]):
            direction = "SHORT"
            entry = max(zona["y0"], zona["y1"])
            sl = entry + abs(zona["y1"]-zona["y0"])
            tp = entry - 2 * abs(zona["y1"]-zona["y0"])
            rr = (entry - tp) / abs(sl - entry) if abs(sl - entry) > 0 else np.nan
            candidates.append({"zona": zona, "direction": direction, "entry": entry, "tp": tp, "sl": sl, "rr": rr})
    if not candidates and fvg_zones:
        fvg = min(fvg_zones, key=lambda z: min(abs(df["Close"].iloc[-1] - z["y0"]), abs(df["Close"].iloc[-1] - z["y1"])))
        if fvg["type"] == "DEMAND":
            direction = "LONG"
            entry = min(fvg["y0"], fvg["y1"])
            sl = entry - abs(fvg["y1"]-fvg["y0"])
            tp = entry + 2 * abs(fvg["y1"]-fvg["y0"])
            rr = (tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else np.nan
        else:
            direction = "SHORT"
            entry = max(fvg["y0"], fvg["y1"])
            sl = entry + abs(fvg["y1"]-fvg["y0"])
            tp = entry - 2 * abs(fvg["y1"]-fvg["y0"])
            rr = (entry - tp) / abs(sl - entry) if abs(sl - entry) > 0 else np.nan
        return {"zona": fvg, "direction": direction, "entry": entry, "tp": tp, "sl": sl, "rr": rr}
    return candidates[0] if candidates else None

def trade_commentary(entry_plan, last_close):
    if not entry_plan:
        return "⏳ Nessun ingresso operativo consigliato sulle zone FVG. Attendere che il prezzo si avvicini a una zona chiave."
    entry = entry_plan["entry"]
    tp = entry_plan["tp"]
    sl = entry_plan["sl"]
    rr = entry_plan["rr"]
    direction = entry_plan["direction"]
    if direction == "LONG":
        txt = f"🟢 **SETUP LONG in zona FVG Demand**\n"
        txt += f"• Entry: {entry:.4f} | TP: {tp:.4f} | SL: {sl:.4f}\n"
        txt += f"• Rischio/Rendimento: {rr:.2f}\n"
        if last_close < entry * 0.995: # prezzo lontano
            txt += "🔸 Il prezzo è sotto la zona FVG: attendere un ritorno in area Demand per valutare un ingresso LONG.\n"
        elif last_close > entry * 1.01:
            txt += "🔸 Il prezzo è sopra la zona FVG: meglio attendere nuovi setup.\n"
        else:
            txt += "✅ Il prezzo è in zona FVG Demand: valuta ingresso LONG, attendi conferma price action.\n"
    else:
        txt = f"🔴 **SETUP SHORT in zona FVG Supply**\n"
        txt += f"• Entry: {entry:.4f} | TP: {tp:.4f} | SL: {sl:.4f}\n"
        txt += f"• Rischio/Rendimento: {rr:.2f}\n"
        if last_close > entry * 1.005: # prezzo lontano
            txt += "🔸 Il prezzo è sopra la zona FVG: attendere un ritorno in area Supply per valutare uno SHORT.\n"
        elif last_close < entry * 0.99:
            txt += "🔸 Il prezzo è sotto la zona FVG: meglio attendere nuovi setup.\n"
        else:
            txt += "✅ Il prezzo è in zona FVG Supply: valuta ingresso SHORT, attendi conferma price action.\n"
    txt += "\n⚠️ Ricorda: i segnali FVG sono più forti se confermati da volumi, oscillatori e price action."
    return txt

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
        last_close = df["Close"].iloc[-1]
        commentary = trade_commentary(entry_plan, last_close)

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
            signal_color = "#d3f9d8"
        elif sum(bear_conds) >= 4:
            trend = "📉 Ribassista"
            signal = "🔴 **Vendita** (SELL)"
            signal_color = "#ffd6d6"
        else:
            trend = "🔄 Laterale/Equilibrio"
            signal = "🟡 **Attendere** (wait)"
            signal_color = "#fffbc1"

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

        # --- REPORT MIGLIORATO ---
        st.markdown(f"""
<style>
.bluebox {{
    background-color:#eaf4fb;
    border-radius:8px;
    padding: 24px 22px;
    margin-bottom:16px;
    font-size:18px;
    color:#08345c;
    border: 1.5px solid #b6d6f7;
}}
.critico {{
    font-weight:bold;
    color:#ef233c;
}}
.critico-swing {{
    color:#08415c;
}}
</style>
""", unsafe_allow_html=True)

        st.markdown(f"""
<div class="bluebox">
<h4>🔍 Valutazione Generale:</h4>
<ul>
<li>Il prezzo attuale di <b>{product_id}</b> è <b>{last_close:.4f} USD</b></li>
<li>Timeframe: <b>{tf_label}</b></li>
<li>Trend di fondo: <b>{trend}</b></li>
<li>Segnale operativo: <b>{signal}</b></li>
</ul>

<h4>📈 Livelli critici osservati:</h4>
<ul>
<li>Swing High: <span class="critico-swing">{swing_high:.4f}</span></li>
<li>Swing Low: <span class="critico-swing">{swing_low:.4f}</span></li>
<li>Equilibrio: <span class="critico-swing">{equilibrio:.4f}</span></li>
<li>Fibonacci: {" | ".join([f"{k}: {v:.2f}" for k, v in fib_levels.items()])}</li>
</ul>
<hr style="margin:14px 0;">
<b>Zone di inversione & manipolazione:</b>
<ul>
<li>{liquidity_text.strip()}</li>
</ul>
<hr style="margin:14px 0;">
<b>Operatività FVG supply/demand:</b>
<br>
<pre style="background:#fff;padding:12px;border-radius:8px;font-size:15px">{commentary}</pre>
<hr style="margin:14px 0;">
<b>Indicatori chiave:</b>
<ul>
<li>RSI: {last['RSI']:.2f}</li>
<li>Momentum: {last['Momentum']:.2f}</li>
<li>PSAR: {last['PSAR']:.4f}</li>
<li>ADX: {last['ADX']:.2f}</li>
<li>MFI: {last['MFI']:.2f}</li>
<li>MACD: {last['MACD']:.4f} / {last['MACD_signal']:.4f}</li>
</ul>
</div>
""", unsafe_allow_html=True)

        st.markdown("<h4>📊 Grafico prezzi, Fibonacci, FVG e volumi</h4>", unsafe_allow_html=True)
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
            color = "rgba(50,200,100,0.20)" if zona["type"] == "DEMAND" else "rgba(255,80,80,0.20)"
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

        st.markdown("<h4>📈 Volumi e ultimi dati</h4>", unsafe_allow_html=True)
        st.line_chart(df["Volume"])
        st.dataframe(df.tail(20))

    else:
        st.warning("Dati insufficienti o errore nel download.")
else:
    st.info("Cerca la crypto, seleziona timeframe e premi Scarica e analizza.")

st.caption("⚠️ Questo report è generato automaticamente dall’AI e NON è un consiglio finanziario. Verifica sempre dati e strategia.")
