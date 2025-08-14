import streamlit as st
import pandas as pd
import ta
import yfinance as yf
from helpers import (
    add_fibonacci_levels,
    add_momentum_indicators,
    add_psar,
    add_dmi_adx,
    add_mfi,
    add_fisher,
    add_trading_signals
)

st.set_page_config("Trade5 Migliorato", layout="wide")
st.title("📈 Trade5 Migliorato")
st.markdown("""
*Analisi tecnica automatizzata con ritracciamento Fibonacci e segnali automatici.*  
Carica un file CSV **oppure** ottieni dati in tempo reale da Yahoo Finance.
""")

data_mode = st.radio("Scegli sorgente dati:", ["Yahoo Finance (tempo reale)", "Carica CSV"])

if data_mode == "Yahoo Finance (tempo reale)":
    ticker = st.text_input("Ticker Yahoo Finance (es. BTC-USD, ETH-USD, AAPL)", value="BTC-USD")
    period = st.selectbox("Periodo", ["1d","5d","1mo","3mo","6mo","1y","2y","5y","max"], index=2)
    interval = st.selectbox("Timeframe", ["1m","2m","5m","15m","30m","60m","90m","1h","1d","1wk"], index=8)
    if st.button("Scarica dati"):
        df = yf.download(ticker, period=period, interval=interval)
        if not df.empty:
            df = df.rename(columns={"Open":"Open","High":"High","Low":"Low","Close":"Close","Volume":"Volume"})
            # Yahoo Finance a volte manca la colonna 'Volume' per certi timeframe
            if "Volume" not in df.columns:
                df["Volume"] = 0
            for fun in [add_fibonacci_levels, add_momentum_indicators, add_psar, add_dmi_adx, add_mfi, add_fisher, add_trading_signals]:
                df = fun(df)
            st.success(f"Dati scaricati per {ticker} ({len(df)} barre)")
        else:
            st.error("Dati non trovati o ticker errato!")
    else:
        df = None
elif data_mode == "Carica CSV":
    uploaded = st.file_uploader("Carica un file CSV (colonne: Date, Open, High, Low, Close, Volume)", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
        for fun in [add_fibonacci_levels, add_momentum_indicators, add_psar, add_dmi_adx, add_mfi, add_fisher, add_trading_signals]:
            df = fun(df)
    else:
        df = None
else:
    df = None

if df is not None and not df.empty:
    st.subheader("Grafico prezzi, Fibonacci, PSAR e segnali")
    import plotly.graph_objs as go
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles"
    ))
    # Fibonacci levels
    for level, value in df.iloc[-1][["Fibo_0.236","Fibo_0.382","Fibo_0.5","Fibo_0.618","Fibo_0.786"]].items():
        fig.add_hline(y=value, line_dash="dot", annotation_text=level, opacity=0.5)
    # PSAR
    fig.add_trace(go.Scatter(x=df.index, y=df["PSAR"], mode="markers", marker=dict(size=3, color="blue"), name="PSAR"))
    # Segnali BUY/SELL
    buy_signals = df[df["Signal"]=="BUY"]
    sell_signals = df[df["Signal"]=="SELL"]
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals["Close"], mode="markers", marker=dict(size=8, color="green", symbol="triangle-up"), name="BUY"))
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals["Close"], mode="markers", marker=dict(size=8, color="red", symbol="triangle-down"), name="SELL"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Ultimi segnali di trading")
    st.dataframe(df[["Open","High","Low","Close","RSI","PSAR","Signal"]].tail(20), use_container_width=True)

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
    st.info("Carica un file o scarica dati Yahoo Finance per iniziare.")

st.caption("⚠️ I segnali sono a solo scopo di studio. Verifica sempre dati e strategia prima di investire.")
