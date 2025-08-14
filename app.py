import streamlit as st
import pandas as pd
import numpy as np
import ta
from helpers import (
    add_fibonacci_levels,
    add_momentum_indicators,
    add_psar,
    add_dmi_adx,
    add_mfi,
    add_fisher
)

st.set_page_config("Trade5 Migliorato", layout="wide")
st.title("📈 Trade5 Migliorato")
st.markdown("""
*Analisi tecnica automatizzata con ritracciamento Fibonacci e indicatori avanzati.*  
Seleziona il tuo file dati (CSV OHLCV) e visualizza segnali e indicatori.
""")

uploaded = st.file_uploader("Carica un file CSV (deve contenere colonne: Date, Open, High, Low, Close, Volume)", type=["csv"])
if uploaded:
    df = pd.read_csv(uploaded)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)

    # Indicatori
    df = add_fibonacci_levels(df)
    df = add_momentum_indicators(df)
    df = add_psar(df)
    df = add_dmi_adx(df)
    df = add_mfi(df)
    df = add_fisher(df)

    st.subheader("Grafico con Fibonacci e PSAR")
    import plotly.graph_objs as go
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Candles"
    ))
    # Fibonacci lines
    for level, value in df.iloc[-1][["Fibo_0.236","Fibo_0.382","Fibo_0.5","Fibo_0.618","Fibo_0.786"]].items():
        fig.add_hline(y=value, line_dash="dot", annotation_text=level, opacity=0.5)
    # PSAR
    fig.add_trace(go.Scatter(x=df.index, y=df["PSAR"], mode="markers", marker=dict(size=3, color="blue"), name="PSAR"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Indicatori Tecnici")
    tabs = st.tabs([
        "Momentum", "DMI/ADX", "MFI", "Fisher"
    ])

    with tabs[0]:
        st.line_chart(df[["Momentum", "ROC", "RSI"]])
    with tabs[1]:
        st.line_chart(df[["+DI", "-DI", "ADX"]])
    with tabs[2]:
        st.line_chart(df[["MFI"]])
    with tabs[3]:
        st.line_chart(df[["Fisher"]])
    st.dataframe(df.tail(20))
else:
    st.info("Carica un file CSV per iniziare.")
