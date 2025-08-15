import streamlit as st
import pandas as pd
import numpy as np
import requests
import ta
from ta.trend import PSARIndicator
import plotly.graph_objs as go

st.set_page_config("Coinbase Advanced Trader Report", layout="wide")
st.title("📊 Coinbase Crypto Advanced Trader Report")

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

def find_swing_high_low(df, lookback=30):
    sh = df["High"][-lookback:].max()
    sl = df["Low"][-lookback:].min()
    eq = (sh + sl) / 2
    return sh, sl, eq

def find_fvg(df):
    fvg_zones = []
    for i in range(2, len(df)):
        if df["Low"].iloc[i] > df["High"].iloc[i - 2]:
            fvg_zones.append({
                "start": df.index[i-2],
                "end": df.index[i],
                "type": "DEMAND",
                "y0": df["High"].iloc[i-2],
                "y1": df["Low"].iloc[i]
            })
        if df["High"].iloc[i] < df["Low"].iloc[i - 2]:
            fvg_zones.append({
                "start": df.index[i-2],
                "end": df.index[i],
                "type": "SUPPLY",
                "y0": df["Low"].iloc[i-2],
                "y1": df["High"].iloc[i]
            })
    return fvg_zones

def detect_demand_supply_zones(df, lookback=30):
    # Area di domanda = minimi chiave, area di offerta = massimi chiave
    demand = []
    supply = []
    lows = df["Low"][-lookback:]
    highs = df["High"][-lookback:]
    # Domanda: Minimi importanti (supporti)
    area_demand = lows[lows <= lows.quantile(0.15)].unique()
    # Offerta: Massimi importanti (resistenze)
    area_supply = highs[highs >= highs.quantile(0.85)].unique()
    # Prendi solo pochi livelli per chiarezza
    return sorted(area_demand)[:3], sorted(area_supply)[-3:]

def detect_resistances_supports(df, lookback=30):
    # Cerca livelli dove il prezzo rimbalza più volte
    prices = df["Close"][-lookback:]
    levels = []
    for p in np.linspace(prices.min(), prices.max(), num=10):
        count = np.sum(np.abs(prices - p) < (prices.max()-prices.min())*0.015)
        if count >= 2:
            levels.append(round(p, 4))
    return sorted(set(levels))

def detect_quasimodo(df, lookback=20):
    # Pattern double top/double bottom (semplificato)
    closes = df["Close"][-lookback:]
    # Double bottom
    if closes.iloc[-1] > closes.min() and (closes == closes.min()).sum() >= 2:
        return "double bottom"
    # Double top
    if closes.iloc[-1] < closes.max() and (closes == closes.max()).sum() >= 2:
        return "double top"
    return None

def pattern_bullish_engulfing(df):
    # Semplice pattern: candle verde che ingloba la rossa precedente
    if len(df) < 2: return False
    prev = df.iloc[-2]
    last = df.iloc[-1]
    return prev["Close"] < prev["Open"] and last["Close"] > last["Open"] and last["Close"] > prev["Open"] and last["Open"] < prev["Close"]

def pattern_bearish_engulfing(df):
    if len(df) < 2: return False
    prev = df.iloc[-2]
    last = df.iloc[-1]
    return prev["Close"] > prev["Open"] and last["Close"] < last["Open"] and last["Open"] > prev["Close"] and last["Close"] < prev["Open"]

def trade_scenarios(df, levels, sh, sl, eq, demand, supply, rsi, lookback=30):
    last_close = df["Close"].iloc[-1]
    scenario_long = ""
    scenario_short = ""
    # LONG
    demand_zone = None
    for d in reversed(demand):
        if last_close >= d*0.98 and last_close <= d*1.015:
            demand_zone = d
            break
    if demand_zone:
        scenario_long += f"- Ingresso possibile su forte reazione bullish fra {demand_zone:.2f} e {last_close:.2f} con pin bar o engulfing bullish su timeframe bassi (5m/15m).\n"
        scenario_long += f"- Target: {supply[-1]:.2f} (prima resistenza principale), poi {sh:.2f}.\n"
        scenario_long += f"- Stop Loss: sotto area domanda ({demand_zone*0.98:.2f}) o swing low ({sl:.2f}).\n"
        scenario_long += f"- Conferme: Volumi in aumento, RSI > 50, pattern double bottom o Quasimodo su tf inferiore.\n"
    else:
        scenario_long += "- Nessuna zona domanda attiva vicina. Attendere nuova occasione."

    # SHORT
    supply_zone = None
    for s in supply[::-1]:
        if last_close <= s*1.02 and last_close >= s*0.985:
            supply_zone = s
            break
    if supply_zone:
        scenario_short += f"- Ingresso possibile su rifiuto deciso da zona offerta {supply_zone:.2f} (engulfing ribassista, spike di volume, chiusura sotto zona).\n"
        scenario_short += f"- Target: {demand[0]:.2f} (area domanda chiave).\n"
        scenario_short += f"- Stop Loss: sopra area offerta ({supply_zone*1.02:.2f}) o swing high ({sh:.2f}).\n"
        scenario_short += f"- Conferme: Volumi in aumento nel ribasso, RSI < 50, pattern double top su tf inferiore.\n"
    else:
        scenario_short += "- Nessuna zona offerta attiva vicina. Attendere nuova occasione."

    return scenario_long, scenario_short

def bias_change_levels(df, supply, demand, sh, sl):
    # Bias bullish sopra la resistenza principale, bearish sotto supporto
    return f"- Cambierei bias in bullish sopra {supply[-1]:.2f} con volumi e chiusura netta.\n- In bearish sotto {demand[0]:.2f} con conferme di rottura."

def general_analysis(df, indicators, sh, sl, eq, supply, demand, rsi, macd, adx):
    price = df["Close"].iloc[-1]
    bull_indicators = [x for x,v in indicators.items() if v == "bullish"]
    bear_indicators = [x for x,v in indicators.items() if v == "bearish"]
    bias = "rialzista" if len(bull_indicators) > len(bear_indicators) else "ribassista"
    txt = f"- La tendenza generale è ancora <b>{bias}</b>, con il prezzo attuale a <b>{price:.2f}</b> USD.\n"
    if bull_indicators:
        txt += f"- Indicatori tecnici principali bullish: {', '.join(bull_indicators)}\n"
    if bear_indicators:
        txt += f"- Indicatori tecnici principali bearish: {', '.join(bear_indicators)}\n"
    txt += f"- Il prezzo si trova tra il punto più alto dell'ultimo swing ({sh:.2f}) e quello più basso ({sl:.2f}), con il livello di equilibrio in area {eq:.2f}.\n"
    txt += "Questi livelli possono essere facilmente manipolati dai grandi operatori.\n"
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
        fib_levels = get_fibonacci_levels(df, lookback)
        sh, sl, eq = find_swing_high_low(df, lookback)
        fvg_zones = find_fvg(df[-lookback:])
        demand, supply = detect_demand_supply_zones(df, lookback)
        key_levels = detect_resistances_supports(df, lookback)
        quasimodo = detect_quasimodo(df, lookback)
        is_bullish_engulf = pattern_bullish_engulfing(df[-3:])
        is_bearish_engulf = pattern_bearish_engulfing(df[-3:])

        indicators = {
            "MACD": "bullish" if df["MACD"].iloc[-1] > df["MACD_signal"].iloc[-1] else "bearish",
            "RSI": "bullish" if df["RSI"].iloc[-1] > 50 else "bearish",
            "Momentum": "bullish" if df["Momentum"].iloc[-1] > 0 else "bearish",
            "PSAR": "bullish" if df["PSAR"].iloc[-1] < df["Close"].iloc[-1] else "bearish",
            "ADX": "bullish" if df["ADX"].iloc[-1] > 20 and df["+DI"].iloc[-1] > df["-DI"].iloc[-1] else "bearish",
            "MFI": "bullish" if df["MFI"].iloc[-1] < 60 else "bearish"
        }
        rsi = df["RSI"].iloc[-1]
        macd = df["MACD"].iloc[-1]
        adx = df["ADX"].iloc[-1]

        # Analisi generale
        gen_analysis = general_analysis(df, indicators, sh, sl, eq, supply, demand, rsi, macd, adx)

        # Livelli chiave
        key_levels_txt = "- Area di domanda sotto il prezzo: " + ", ".join([f"{x:.2f}" for x in demand]) + " (supporto chiave).\n"
        key_levels_txt += "- Area di offerta sopra il prezzo: " + ", ".join([f"{x:.2f}" for x in supply]) + " (resistenza chiave).\n"
        key_levels_txt += "- Altri livelli chiave: " + ", ".join([f"{x:.2f}" for x in key_levels]) + "\n"
        key_levels_txt += "- Area di squilibrio rialzista tra {:.2f} e {:.2f} (se mantenuta, possibile rimbalzo).".format(eq - (sh-sl)*0.1, eq + (sh-sl)*0.1)

        # Scenari trade
        scenario_long, scenario_short = trade_scenarios(df, key_levels, sh, sl, eq, demand, supply, rsi)
        bias_change_txt = bias_change_levels(df, supply, demand, sh, sl)

        # Conferme
        conferme = []
        if is_bullish_engulf:
            conferme.append("Pin bar o engulfing bullish in zona chiave (long)")
        if is_bearish_engulf:
            conferme.append("Engulfing ribassista in zona chiave (short)")
        if quasimodo:
            conferme.append(f"Pattern {quasimodo} su timeframe inferiore")
        if df["Volume"].iloc[-1] > df["Volume"][-lookback:].mean()*1.2:
            conferme.append("Volume in aumento relativo all'impulso")
        if rsi > 50:
            conferme.append("RSI sopra 50 (long)")
        elif rsi < 50:
            conferme.append("RSI sotto 50 (short)")

        st.markdown(f"""
<style>
.tgbox {{
    background-color:#eaf4fb;
    border-radius:8px;
    padding: 24px 22px;
    margin-bottom:16px;
    font-size:19px;
    color:#08345c;
    border: 1.5px solid #b6d6f7;
}}
.keybox {{
    background-color:#f3f9f4;
    border-radius:8px;
    padding: 12px 15px;
    margin-bottom:10px;
    font-size:17px;
    color:#0a3d1a;
    border: 1.5px solid #bde0c6;
}}
</style>
""", unsafe_allow_html=True)

        st.markdown(f"""
<div class="tgbox">
<h4>🔍 Analisi generale avanzata</h4>
{gen_analysis}
<br>
<hr>
<h4>📊 Livelli critici:</h4>
<div class="keybox">{key_levels_txt}</div>
<h4>📈 Scenari di trade</h4>
<b>🟢 Scenario LONG:</b><br>
{scenario_long}
<br>
<b>🔴 Scenario SHORT:</b><br>
{scenario_short}
<br>
<hr>
<b>✏️ Cambiamento bias:</b><br>
{bias_change_txt}
<br>
<hr>
<b>📝 Conferme da attendere:</b><br>
<ul>
""" + "\n".join([f"<li>{c}</li>" for c in conferme]) + """
</ul>
</div>
""", unsafe_allow_html=True)

        st.markdown("<h4>📊 Grafico prezzi, livelli chiave e volumi</h4>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"
        ))
        # Fibonacci
        color_map = {
            "0%": "purple", "23.6%": "blue", "38.2%": "teal", "50%": "orange",
            "61.8%": "green", "78.6%": "red", "100%": "black"
        }
        for k, v in fib_levels.items():
            fig.add_hline(y=v, line_dash="dot", line_color=color_map.get(k, "gray"), annotation_text=f"Fib {k}")

        # Domanda/offerta
        for d in demand:
            fig.add_hline(y=d, line_color="green", line_dash="dash", annotation_text="Domanda")
        for s in supply:
            fig.add_hline(y=s, line_color="red", line_dash="dash", annotation_text="Offerta")

        # Swing
        fig.add_hline(y=sh, line_color="blue", line_dash="dot", annotation_text="Swing High")
        fig.add_hline(y=sl, line_color="blue", line_dash="dot", annotation_text="Swing Low")
        fig.add_hline(y=eq, line_color="gray", line_dash="dot", annotation_text="Equilibrio")

        # FVG
        for zona in fvg_zones:
            color = "rgba(50,200,100,0.12)" if zona["type"] == "DEMAND" else "rgba(255,80,80,0.12)"
            fig.add_vrect(x0=zona["start"], x1=zona["end"], y0=zona["y0"], y1=zona["y1"], fillcolor=color, line_width=0, annotation_text=zona["type"])

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<h4>📈 Volumi e ultimi dati</h4>", unsafe_allow_html=True)
        st.line_chart(df["Volume"])
        st.dataframe(df.tail(20))

    else:
        st.warning("Dati insufficienti o errore nel download.")
else:
    st.info("Cerca la crypto, seleziona timeframe e premi Scarica e analizza.")

st.caption("⚠️ Questo report è generato automaticamente dall’AI e NON è un consiglio finanziario. Verifica sempre dati e strategia.")
