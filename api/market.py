import json, math
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import yfinance as yf
import pandas as pd

def num(v):
    try:
        x=float(v)
        return None if math.isnan(x) or math.isinf(x) else x
    except Exception: return None

def payload(symbol,period,interval):
    df=yf.download(symbol,period=period,interval=interval,auto_adjust=False,progress=False,threads=False)
    if df is None or df.empty: raise ValueError("Nenhum dado encontrado para esse ativo e período.")
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"].astype(float)
    df["SMA20"]=c.rolling(20).mean(); df["SMA50"]=c.rolling(50).mean(); df["EMA20"]=c.ewm(span=20,adjust=False).mean()
    d=c.diff(); gain=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); loss=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    df["RSI"]=100-(100/(1+gain/loss.replace(0,float("nan"))))
    df["MACD"]=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    df["SIGNAL"]=df["MACD"].ewm(span=9,adjust=False).mean()
    rows=[]
    for ix,r in df.iterrows():
        t=pd.Timestamp(ix); t=t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        row={"time":t.isoformat(),"open":num(r.get("Open")),"high":num(r.get("High")),"low":num(r.get("Low")),"close":num(r.get("Close")),"volume":int(num(r.get("Volume")) or 0),"sma20":num(r.get("SMA20")),"sma50":num(r.get("SMA50")),"ema20":num(r.get("EMA20")),"rsi":num(r.get("RSI")),"macd":num(r.get("MACD")),"signal":num(r.get("SIGNAL"))}
        if all(row[k] is not None for k in ("open","high","low","close")): rows.append(row)
    return {"symbol":symbol,"currency":"BRL" if symbol.endswith(".SA") else "USD","candles":rows,"last":rows[-1] if rows else None}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q=parse_qs(urlparse(self.path).query); s=q.get("symbol",["PETR4.SA"])[0].upper()
            p=q.get("period",["6mo"])[0]; i=q.get("interval",["1d"])[0]
            if p not in {"1d","5d","1mo","3mo","6mo","1y","2y","5y"} or i not in {"5m","15m","30m","60m","1d","1wk"}: raise ValueError("Período ou intervalo inválido.")
            out=payload(s,p,i); code=200
        except Exception as e: out={"error":str(e)}; code=400
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(json.dumps(out,ensure_ascii=False).encode())
