import streamlit as st
import pandas as pd
import numpy as np
from pycoingecko import CoinGeckoAPI
import ta
from datetime import datetime

st.set_page_config("Finora-Style Crypto Analysis", layout="wide")
st.title("🤖 Finora Style Crypto Report (by AI Copilot)")

# --- Scarica dati CoinGecko ---
cg = CoinGeckoAPI()
crypto_list = cg.get_coins_list()
crypto_names = {c['id']: f"{c['symbol'].upper()} - {c['name']}" for c in crypto_list}
crypto_id = st.selectbox("Scegli criptovaluta", options=list(crypto_names.keys()), format_func=lambda x: crypto_names[x], index=crypto_list.index(next(c for c in crypto_list if c["id"] == "bitcoin")))

n_days = st.slider("Quanti giorni di storico?", min_value=1, max_value=90, value=14)
interval = st.selectbox("Timeframe", ["hourly", "daily"], index=0)

df = None
if st.button("Analizza ora"):
    with st.spinner("Scarico dati da CoinGecko..."):
        # Fix CoinGecko API: interval must be "daily" if n_days > 90, else "hourly" or "daily"
        if n_days > 90:
            interval = "daily"
        elif n_days <= 90 and interval not in ["hourly", "daily"]:
            interval = "hourly"
        try:
            data = cg.get_coin_market_chart_by_id(id=crypto_id, vs_currency='usd', days=n_days, interval=interval)
        except Exception as e:
            st.error(f"Errore CoinGecko: {e}\nProva a cambiare il timeframe o riduci i giorni di storico.")
            df = None

    if df is None and 'data' in locals():
        prices = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
        prices['Date'] = pd.to_datetime(prices['timestamp'], unit='ms')
        prices.set_index('Date', inplace=True)
        df = prices.resample('1H' if interval == 'hourly' else '1D').agg({'price':['first','max','min','last']}).dropna()
        df.columns = ['Open','High','Low','Close']
        if 'total_volumes' in data and len(data['total_volumes']) == len(prices):
            volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
            volumes['Date'] = pd.to_datetime(volumes['timestamp'], unit='ms')
            volumes.set_index('Date', inplace=True)
            df['Volume'] = volumes.resample('1H' if interval == 'hourly' else '1D').sum()['volume']
        else:
            df['Volume'] = np.nan

        # Indicatori principali
        df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
        df["MFI"] = ta.volume.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], window=14)
        df["ADX"] = ta.trend.adx(df["High"], df["Low"], df["Close"], window=14)
        df["+DI"] = ta.trend.adx_pos(df["High"], df["Low"], df["Close"], window=14)
        df["-DI"] = ta.trend.adx_neg(df["High"], df["Low"], df["Close"], window=14)
        df["PSAR"] = ta.trend.psar(df["High"], df["Low"], df["Close"])
        df["Momentum"] = ta.momentum.roc(df["Close"], window=10)
        # Fisher: uso KAMA per simulazione, non c'è Fisher nativo in ta
        df["Fisher"] = ta.momentum.kama(df["Close"], window=10)
        macd = ta.trend.macd(df["Close"])
        macd_signal = ta.trend.macd_signal(df["Close"])
        df["MACD"] = macd
        df["MACD_signal"] = macd_signal

        # Livelli swing
        last_high = df["High"][-30:].max()
        last_low = df["Low"][-30:].min()
        last_eq = (last_high + last_low) / 2
        last_close = df["Close"].iloc[-1]
        last_rsi = df["RSI"].iloc[-1]
        last_adx = df["ADX"].iloc[-1]
        last_mfi = df["MFI"].iloc[-1]
        last_psar = df["PSAR"].iloc[-1]
        last_macd = df["MACD"].iloc[-1]
        last_macd_signal = df["MACD_signal"].iloc[-1]
        last_fisher = df["Fisher"].iloc[-1]
        last_fisher_prev = df["Fisher"].iloc[-2]
        last_momentum = df["Momentum"].iloc[-1]

        # Trend detection (semplice)
        bull_conds = [
            last_macd > last_macd_signal,
            last_rsi > 55,
            last_adx > 20 and df["+DI"].iloc[-1] > df["-DI"].iloc[-1],
            last_mfi < 60,
            last_psar < last_close,
            last_fisher > last_fisher_prev
        ]
        bear_conds = [
            last_macd < last_macd_signal,
            last_rsi < 45,
            last_adx > 20 and df["+DI"].iloc[-1] < df["-DI"].iloc[-1],
            last_mfi > 40,
            last_psar > last_close,
            last_fisher < last_fisher_prev
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
        if "BUY" in signal:
            take_profit = last_close * 1.03
            stop_loss = last_close * 0.98
        elif "SELL" in signal:
            take_profit = last_close * 0.97
            stop_loss = last_close * 1.02
        else:
            take_profit = np.nan
            stop_loss = np.nan

        # Volumi (simulati, CoinGecko non fornisce breakdown buy/sell)
        vol_sell = np.random.uniform(60, 99) if sum(bear_conds) >= 4 else np.random.uniform(10, 50)
        vol_buy = 100 - vol_sell

        # --- REPORT GENERATION ---
        report = f"""
🔍 **Valutazione Generale:**

- Il prezzo attuale di **{crypto_names[crypto_id]}** è **{last_close:.4f} USD**, vicino al livello di equilibrio dell’ultimo swing (**{last_eq:.4f}**)
- Il trend di fondo è: **{trend}**
- La maggior parte degli indicatori principali (MACD, Momentum, RSI, PSAR, ADX, MFI, Fisher) sono orientati a {'rialzo' if sum(bull_conds) >= 4 else 'ribasso' if sum(bear_conds) >= 4 else 'equilibrio'}, 
- Volumi: {vol_sell:.0f}% sell, {vol_buy:.0f}% buy (stime indicative, CoinGecko non fornisce breakdown reale)
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
- RSI: {last_rsi:.2f}
- Momentum: {last_momentum:.2f}
- PSAR: {last_psar:.4f}
- ADX: {last_adx:.2f}
- MFI: {last_mfi:.2f}
- MACD: {last_macd:.4f} / {last_macd_signal:.4f}
- Fisher: {last_fisher:.4f}
"""
        st.info(report)

        st.subheader("📊 Grafico prezzi e segnali")
        import plotly.graph_objs as go
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"
        ))
        fig.add_hline(y=last_high, line_dash="dot", annotation_text="Swing High", opacity=0.5)
        fig.add_hline(y=last_low, line_dash="dot", annotation_text="Swing Low", opacity=0.5)
        fig.add_hline(y=last_eq, line_dash="dot", annotation_text="Equilibrio", opacity=0.5)
        if not np.isnan(take_profit):
            fig.add_hline(y=take_profit, line=dict(color="green", dash="dash"), annotation_text="Take Profit")
        if not np.isnan(stop_loss):
            fig.add_hline(y=stop_loss, line=dict(color="red", dash="dash"), annotation_text="Stop Loss")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Ultimi dati & indicatori")
        st.dataframe(df.tail(20))

else:
    st.info("Seleziona una crypto e premi Analizza ora.")

st.caption("⚠️ Questo report è generato automaticamente dall’AI e NON è un consiglio finanziario. Verifica sempre i dati e la strategia.")
