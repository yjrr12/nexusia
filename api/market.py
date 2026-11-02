import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import yfinance as yf
import pandas as pd


def calculate_indicators(df):
    close = df["Close"]

    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["EMA20"] = close.ewm(span=20, adjust=False).mean()

    delta = close.diff()

    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()

    rs = gain / loss.replace(0, float("nan"))

    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    df["MACD"] = ema12 - ema26
    df["MACDSignal"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    return df


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)

            ticker = query.get("ticker", ["AAPL"])[0]
            period = query.get("period", ["6mo"])[0]

            allowed = [
                "1mo", "3mo", "6mo",
                "1y", "2y", "5y"
            ]

            if period not in allowed:
                period = "6mo"

            df = yf.Ticker(ticker).history(
                period=period,
                interval="1d"
            )

            if df.empty:
                self.send_json(
                    404,
                    {"error": "Ativo não encontrado"}
                )
                return

            df = calculate_indicators(df)

            rows = []

            for date, row in df.tail(400).iterrows():

                def value(column):
                    v = row.get(column)

                    if pd.isna(v):
                        return None

                    return float(v)

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": value("Open"),
                    "high": value("High"),
                    "low": value("Low"),
                    "close": value("Close"),
                    "volume": value("Volume"),
                    "sma20": value("SMA20"),
                    "sma50": value("SMA50"),
                    "ema20": value("EMA20"),
                    "rsi": value("RSI"),
                    "macd": value("MACD"),
                    "macdSignal": value("MACDSignal")
                })

            last = rows[-1]
            previous = rows[-2]["close"] if len(rows) > 1 else last["close"]

            change = (
                ((last["close"] / previous) - 1) * 100
                if previous else 0
            )

            self.send_json(200, {
                "ticker": ticker,
                "price": last["close"],
                "change": change,
                "data": rows
            })

        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def send_json(self, status, data):
        body = json.dumps(
            data,
            allow_nan=False
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.send_header(
            "Cache-Control",
            "s-maxage=60, stale-while-revalidate=120"
        )
        self.end_headers()
        self.wfile.write(body)