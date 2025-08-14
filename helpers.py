import numpy as np
import pandas as pd
import ta

def add_fibonacci_levels(df):
    lookback = 100 if len(df) > 100 else len(df)
    max_price = df["High"].tail(lookback).max()
    min_price = df["Low"].tail(lookback).min()
    diff = max_price - min_price
    for level, ratio in zip(["Fibo_0.236", "Fibo_0.382", "Fibo_0.5", "Fibo_0.618", "Fibo_0.786"], [0.236, 0.382, 0.5, 0.618, 0.786]):
        df[level] = max_price - ratio * diff
    return df

def add_momentum_indicators(df):
    df["Momentum"] = ta.momentum.roc(df["Close"], window=10)
    df["ROC"] = ta.momentum.roc(df["Close"], window=5)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    return df

def add_psar(df):
    psar = ta.trend.psar(df["High"], df["Low"], df["Close"])
    df["PSAR"] = psar
    return df

def add_dmi_adx(df):
    df["+DI"] = ta.trend.adx_pos(df["High"], df["Low"], df["Close"], window=14)
    df["-DI"] = ta.trend.adx_neg(df["High"], df["Low"], df["Close"], window=14)
    df["ADX"] = ta.trend.adx(df["High"], df["Low"], df["Close"], window=14)
    return df

def add_mfi(df):
    df["MFI"] = ta.volume.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], window=14)
    return df

def add_fisher(df):
    length = 10
    hl2 = (df["High"] + df["Low"]) / 2
    min_low = hl2.rolling(length).min()
    max_high = hl2.rolling(length).max()
    value = 0.33 * 2 * ((hl2 - min_low) / (max_high - min_low + 1e-9) - 0.5)
    value = value.fillna(0)
    fish = value.copy()
    for i in range(1, len(value)):
        fish.iloc[i] = 0.5 * value.iloc[i] + 0.5 * fish.iloc[i-1]
    df["Fisher"] = fish
    return df

def add_trading_signals(df):
    df["Signal"] = "HOLD"
    df["TakeProfit"] = np.nan
    df["StopLoss"] = np.nan

    # Condizioni BUY
    cond_buy = (
        (df["RSI"] < 35) &
        (df["PSAR"] < df["Close"]) &
        (df["ADX"] > 20) & (df["+DI"] > df["-DI"]) &
        (df["MFI"] < 35) &
        (df["Fisher"] > df["Fisher"].shift(1))
    )
    # Condizioni SELL
    cond_sell = (
        (df["RSI"] > 65) &
        (df["PSAR"] > df["Close"]) &
        (df["ADX"] > 20) & (df["-DI"] > df["+DI"]) &
        (df["MFI"] > 65) &
        (df["Fisher"] < df["Fisher"].shift(1))
    )
    df.loc[cond_buy, "Signal"] = "BUY"
    df.loc[cond_sell, "Signal"] = "SELL"
    # Take Profit e Stop Loss (solo per segnali)
    buy_idx = df.index[df["Signal"] == "BUY"]
    sell_idx = df.index[df["Signal"] == "SELL"]
    df.loc[buy_idx, "TakeProfit"] = df.loc[buy_idx, "Close"] * 1.03
    df.loc[buy_idx, "StopLoss"] = df.loc[buy_idx, "Close"] * 0.98
    df.loc[sell_idx, "TakeProfit"] = df.loc[sell_idx, "Close"] * 0.97
    df.loc[sell_idx, "StopLoss"] = df.loc[sell_idx, "Close"] * 1.02
    return df
