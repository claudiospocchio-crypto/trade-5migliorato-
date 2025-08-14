import streamlit as st
import pandas as pd
import numpy as np
from pycoingecko import CoinGeckoAPI
from datetime import datetime, timedelta
from helpers import (
    add_fibonacci_levels,
    add_momentum_indicators,
    add_psar,
    add_dmi_adx,
    add_mfi,
    add_fisher,
    add_trading_signals
)

st.set_page_config("Trade5 Migliorato CoinGecko", layout="wide")
st.title("📈 Trade5 Migliorato - CoinGecko Live Crypto Signals")

cg = CoinGeckoAPI()
crypto_list = cg.get_coins_list()
crypto_names = {c['id']: c['symbol'].upper() + ' - ' + c['name'] for c in crypto_list}
crypto_id = st.selectbox("Scegli criptovaluta (CoinGecko)", options=list(crypto_names.keys()), format_func=lambda x: crypto_names[x], index=crypto_list.index(next(c for c in crypto_list if c["id"] == "bitcoin")))

n_days = st.slider("Quanti giorni di storico?", min_value=1, max_value=90, value=30)
interval = st.selectbox("Timeframe", ["hourly", "daily"], index=1)

df = None
if st.button("Scarica dati CoinGecko"):
    with st.spinner("Scarico dati..."):
        data = cg.get_coin_market_chart_by_id(id=crypto_id, vs_currency='usd', days=n_days, interval=interval)
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
        # Indicatori e segnali
        for fun in [add_fibonacci_levels, add_momentum_indicators, add_psar, add_dmi_adx, add_mfi, add_fisher, add_trading_signals]:
            df = fun(df)
        st.success(f"Dati scaricati per {crypto_names[crypto_id]} ({len(df)} barre).")

if df is not None and not df.empty:
    st.subheader("Grafico prezzi, Fibonacci, segnali e livelli TP/SL")
    import plotly.graph_objs as go
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"
    ))
    for level, value in df.iloc[-1][["Fibo_0.236","Fibo_0.382","Fibo_0.5","Fibo_0.618","Fibo_0.786"]].items():
        fig.add_hline(y=value, line_dash="dot", annotation_text=level, opacity=0.5)
    fig.add_trace(go.Scatter(x=df.index, y=df["PSAR"], mode="markers", marker=dict(size=3, color="blue"), name="PSAR"))
    buy_signals = df[df["Signal"]=="BUY"]
    sell_signals = df[df["Signal"]=="SELL"]
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals["Close"], mode="markers", marker=dict(size=8, color="green", symbol="triangle-up"), name="BUY"))
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals["Close"], mode="markers", marker=dict(size=8, color="red", symbol="triangle-down"), name="SELL"))
    # TP/SL livelli
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals["TakeProfit"], mode="markers", marker=dict(size=7, color="orange"), name="TP BUY"))
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals["StopLoss"], mode="markers", marker=dict(size=7, color="black"), name="SL BUY"))
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals["TakeProfit"], mode="markers", marker=dict(size=7, color="orange"), name="TP SELL"))
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals["StopLoss"], mode="markers", marker=dict(size=7, color="black"), name="SL SELL"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Ultimi segnali, TP e SL")
    st.dataframe(df[["Open","High","Low","Close","RSI","PSAR","ADX","MFI","Fisher","Signal","TakeProfit","StopLoss"]].tail(20), use_container_width=True)

    st.subheader("Indicatori Tecnici")
    tabs = st.tabs(["Momentum", "DMI/ADX", "MFI", "Fisher"])
    with tabs[0]:
        st.line_chart(df[["Momentum","ROC","RSI"]])
    with tabs[1]:
        st.line_chart(df[["+DI","-DI","ADX"]])
    with tabs[2]:
        st.line_chart(df[["MFI"]])
    with tabs[3]:
        st.line_chart(df[["Fisher"]])
else:
    st.info("Scarica dati CoinGecko per iniziare.")

st.caption("⚠️ I segnali sono a solo scopo di studio. Verifica sempre dati e strategia prima di investire.")
