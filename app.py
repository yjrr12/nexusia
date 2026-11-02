import os, ssl, smtplib, threading, time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Nexus AI", page_icon="📈", layout="wide")
st.markdown("""
<style>
.stApp{background:#0b1020;color:#e8eefc}
[data-testid="stSidebar"]{background:#10182b}
[data-testid="stMetric"]{background:#111b30;border:1px solid #263653;padding:12px;border-radius:12px}
</style>
""", unsafe_allow_html=True)
st.title("📈 Nexus AI")
st.caption("Mercado • Análise técnica • Nexus AI (Groq) • Alertas por e-mail")

ASSETS = {
    "Ações brasileiras":{"PETR4.SA":"Petrobras PN","VALE3.SA":"Vale","ITUB4.SA":"Itaú Unibanco","BBDC4.SA":"Bradesco PN","BBAS3.SA":"Banco do Brasil","WEGE3.SA":"WEG","ABEV3.SA":"Ambev","BOVA11.SA":"ETF Ibovespa"},
    "Índices":{"^BVSP":"Ibovespa","^GSPC":"S&P 500","^IXIC":"Nasdaq Composite","^DJI":"Dow Jones","^VIX":"Índice VIX"},
    "Ações americanas":{"AAPL":"Apple","MSFT":"Microsoft","NVDA":"NVIDIA","GOOGL":"Alphabet","AMZN":"Amazon","TSLA":"Tesla","META":"Meta"},
    "Criptomoedas":{"BTC-USD":"Bitcoin","ETH-USD":"Ethereum","SOL-USD":"Solana","XRP-USD":"XRP","DOGE-USD":"Dogecoin"}
}
NAMES = {k:v for group in ASSETS.values() for k,v in group.items()}
for k,v in {"chat_history":[],"logs":[],"monitor_event":None,"monitor_thread":None,"monitor_running":False,"last_alerts":set()}.items():
    if k not in st.session_state: st.session_state[k]=v

@st.cache_data(ttl=60, show_spinner=False)
def history(ticker, period="6mo", interval="1d"):
    try:
        d=yf.Ticker(ticker).history(period=period,interval=interval)
        return d if d is not None else pd.DataFrame()
    except Exception: return pd.DataFrame()

def snapshot(ticker):
    try:
        d=yf.Ticker(ticker).history(period="5d",interval="1d")
        c=d["Close"].dropna()
        if len(c)<1:return None
        p=float(c.iloc[-1]); prev=float(c.iloc[-2]) if len(c)>1 else p
        return p,((p/prev)-1)*100 if prev else 0
    except Exception:return None

def money(ticker,p):
    if ticker.endswith(".SA") or ticker=="^BVSP":return "R$ "+f"{p:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    return f"{p:,.4f}" if ticker.endswith("-USD") else f"{p:,.2f}"

def indicators(d):
    d=d.copy(); c=d["Close"]
    d["SMA 20"]=c.rolling(20).mean(); d["SMA 50"]=c.rolling(50).mean()
    d["EMA 20"]=c.ewm(span=20,adjust=False).mean()
    delta=c.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
    rs=gain/loss.replace(0,float("nan")); d["RSI"]=100-(100/(1+rs))
    d["MACD"]=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    d["Sinal MACD"]=d["MACD"].ewm(span=9,adjust=False).mean()
    return d

def send_mail(sender,password,recipient,subject,body):
    if not all([sender.strip(),password.strip(),recipient.strip()]): raise ValueError("Preencha remetente, senha de aplicativo e destinatário.")
    m=EmailMessage(); m["From"]=sender.strip(); m["To"]=recipient.strip(); m["Subject"]=subject; m.set_content(body)
    try:
        with smtplib.SMTP("smtp.gmail.com",587,timeout=20) as s:
            s.ehlo(); s.starttls(context=ssl.create_default_context()); s.login(sender.strip(),password.replace(" ","").strip()); s.send_message(m)
    except Exception:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,timeout=20,context=ssl.create_default_context()) as s:
            s.login(sender.strip(),password.replace(" ","").strip()); s.send_message(m)

def monitor(config,event,logs,last_alerts):
    while not event.is_set():
        for ticker in config["tickers"]:
            if event.is_set(): break
            snap=snapshot(ticker)
            if not snap: continue
            price,change=snap
            if abs(change)<config["threshold"]: continue
            direction="alta" if change>0 else "queda"
            key=f"{datetime.now().date()}:{ticker}:{direction}"
            if key in last_alerts: continue
            subject=f"Nexus AI: {direction.upper()} de {abs(change):.2f}% — {NAMES.get(ticker,ticker)}"
            body=f"Alerta Nexus AI\\nAtivo: {NAMES.get(ticker,ticker)} ({ticker})\\nPreço: {price}\\nVariação diária aproximada: {change:+.2f}%\\nHora: {datetime.now():%d/%m/%Y %H:%M:%S}\\n\\nInformativo, não é recomendação de investimento."
            try:
                send_mail(config["sender"],config["password"],config["recipient"],subject,body)
                status="Enviado"; detail=subject; last_alerts.add(key)
            except Exception as e: status="Erro"; detail=str(e)[:250]
            logs.append({"Data":datetime.now().strftime("%d/%m/%Y %H:%M:%S"),"Ativo":ticker,"Tipo":direction,"Variação (%)":round(change,2),"Status":status,"Detalhe":detail})
        event.wait(config["seconds"])

def ask_groq(messages, model, api_key):
    if not api_key or not api_key.strip():
        raise ValueError("Configure a chave GROQ_API_KEY nas variáveis de ambiente ou nos Secrets do Streamlit.")
    r=requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.4},
        timeout=90,
    )
    r.raise_for_status()
    data=r.json()
    return data["choices"][0]["message"]["content"]

with st.sidebar:
    st.header("Navegação")
    page=st.radio("Abrir",["Mercado","Análise técnica","Nexus AI","E-mail e alertas","Registros","Sobre"])
    st.divider()
    st.caption("Dados via Yahoo Finance. Podem ter atraso.")

if page=="Mercado":
    st.subheader("Mercado")
    a,b=st.columns([3,1])
    group=a.selectbox("Categoria",list(ASSETS))
    period=b.selectbox("Período",["1mo","3mo","6mo","1y","2y","5y"],index=2)
    if st.button("Atualizar cotações"): history.clear()
    rows=[]
    with st.spinner("Consultando cotações..."):
        for t,n in ASSETS[group].items():
            x=snapshot(t)
            if x: rows.append({"Ativo":n,"Ticker":t,"Preço":money(t,x[0]),"Variação diária (%)":x[1]})
    if rows: st.dataframe(pd.DataFrame(rows).style.format({"Variação diária (%)":"{:+.2f}%"}),use_container_width=True,hide_index=True)
    else: st.warning("Sem cotações no momento.")
    t=st.selectbox("Ativo para o gráfico",list(ASSETS[group]),format_func=lambda x:f"{ASSETS[group][x]} ({x})")
    d=history(t,period)
    if not d.empty:
        f=go.Figure(go.Scatter(x=d.index,y=d["Close"],mode="lines",name="Fechamento"))
        f.update_layout(template="plotly_dark",height=420,title=f"{NAMES[t]} — fechamento")
        st.plotly_chart(f,use_container_width=True)

elif page=="Análise técnica":
    st.subheader("Análise técnica")
    t=st.selectbox("Ativo",list(NAMES),format_func=lambda x:f"{NAMES[x]} ({x})")
    period=st.selectbox("Período",["1mo","3mo","6mo","1y","2y","5y"],index=2)
    d=history(t,period)
    if d.empty: st.warning("Sem dados para esse ativo.")
    else:
        d=indicators(d); last=d.iloc[-1]; prev=d["Close"].iloc[-2] if len(d)>1 else last["Close"]
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Último fechamento",money(t,float(last["Close"])))
        c2.metric("Variação",f"{(last['Close']/prev-1)*100:+.2f}%")
        c3.metric("RSI (14)",f"{last['RSI']:.2f}" if pd.notna(last["RSI"]) else "N/D")
        c4.metric("MACD",f"{last['MACD']:.4f}" if pd.notna(last["MACD"]) else "N/D")
        f=go.Figure()
        f.add_trace(go.Candlestick(x=d.index,open=d["Open"],high=d["High"],low=d["Low"],close=d["Close"],name="Preço"))
        for col in ["SMA 20","SMA 50","EMA 20"]: f.add_trace(go.Scatter(x=d.index,y=d[col],name=col,mode="lines"))
        f.update_layout(template="plotly_dark",height=500,xaxis_rangeslider_visible=False)
        st.plotly_chart(f,use_container_width=True)
        x,y=st.columns(2)
        with x:
            r=go.Figure(go.Scatter(x=d.index,y=d["RSI"],name="RSI")); r.add_hline(y=70,line_dash="dash"); r.add_hline(y=30,line_dash="dash")
            r.update_layout(template="plotly_dark",title="RSI (14)",height=280,yaxis_range=[0,100]); st.plotly_chart(r,use_container_width=True)
        with y:
            m=go.Figure(); m.add_trace(go.Scatter(x=d.index,y=d["MACD"],name="MACD")); m.add_trace(go.Scatter(x=d.index,y=d["Sinal MACD"],name="Sinal"))
            m.update_layout(template="plotly_dark",title="MACD",height=280); st.plotly_chart(m,use_container_width=True)
        st.caption("Indicadores históricos não garantem resultados futuros.")

elif page=="Nexus AI":
    st.subheader("Chat com Nexus AI (Groq)")
    model=st.selectbox("Modelo Groq", ["llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-8b-instant"], index=0)
    api_key=st.text_input("Chave da API Groq (ou configure GROQ_API_KEY)", type="password", value="")
    if not api_key:
        try: api_key=st.secrets.get("GROQ_API_KEY", "")
        except Exception: api_key=os.getenv("GROQ_API_KEY", "")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    prompt=st.chat_input("Pergunte sobre mercado, indicadores ou risco...")
    if prompt:
        st.session_state.chat_history.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        messages=[{"role":"system","content":"Você é o Nexus AI, assistente de educação financeira. Responda em português brasileiro, explique riscos e não prometa retornos nem dê recomendações personalizadas definitivas."}]+st.session_state.chat_history[-16:]
        with st.chat_message("assistant"):
            try:
                with st.spinner("Consultando o Groq..."): answer=ask_groq(messages,model,api_key)
                st.markdown(answer)
            except Exception as e: answer=f"Erro ao consultar o Groq: {e}. Verifique a chave GROQ_API_KEY e o modelo selecionado."; st.error(answer)
        st.session_state.chat_history.append({"role":"assistant","content":answer})
    if st.button("Limpar conversa"): st.session_state.chat_history=[]; st.rerun()

elif page=="E-mail e alertas":
    st.subheader("E-mail e alertas automáticos")
    st.info("O monitoramento só funciona enquanto o Streamlit estiver rodando e o computador ligado.")
    with st.expander("Como configurar o Gmail"):
        st.markdown("Ative a verificação em duas etapas na Conta Google e crie uma **senha de app**. Use essa senha aqui, não a senha normal da conta.")
    with st.form("email_form"):
        sender=st.text_input("Gmail remetente")
        password=st.text_input("Senha de aplicativo",type="password")
        recipient=st.text_input("E-mail destinatário")
        threshold=st.number_input("Variação mínima (%)",min_value=0.5,max_value=30.0,value=5.0,step=0.5)
        minutes=st.selectbox("Intervalo de verificação (minutos)",[5,10,15,30,60])
        tickers=st.multiselect("Ativos monitorados",list(NAMES),default=["PETR4.SA","VALE3.SA","^BVSP","AAPL","NVDA","BTC-USD"],format_func=lambda x:f"{NAMES[x]} ({x})")
        x,y=st.columns(2)
        test=x.form_submit_button("Enviar e-mail de teste",use_container_width=True)
        start=y.form_submit_button("Iniciar monitoramento",use_container_width=True)
    if test or start:
        if not sender or not password or not recipient: st.error("Preencha os três campos de e-mail.")
        elif start and not tickers: st.error("Escolha ao menos um ativo.")
        else:
            if test:
                try:
                    send_mail(sender,password,recipient,"Nexus AI — teste","Seu e-mail do Nexus AI está configurado corretamente.")
                    st.success("E-mail de teste enviado.")
                    st.session_state.logs.append({"Data":datetime.now().strftime("%d/%m/%Y %H:%M:%S"),"Ativo":"—","Tipo":"Teste","Variação (%)":0,"Status":"Enviado","Detalhe":recipient})
                except Exception as e: st.error(f"Falha no teste: {e}")
            if start:
                if st.session_state.monitor_event is not None: st.session_state.monitor_event.set()
                event=threading.Event()
                config={"sender":sender,"password":password,"recipient":recipient,"threshold":float(threshold),"seconds":int(minutes)*60,"tickers":tickers}
                thread=threading.Thread(target=monitor,args=(config,event,st.session_state.logs,st.session_state.last_alerts),daemon=True)
                st.session_state.monitor_event=event; st.session_state.monitor_thread=thread; st.session_state.monitor_running=True
                thread.start(); st.success("Monitoramento iniciado. Deixe o app aberto.")
    if st.session_state.monitor_running: st.success("Monitoramento iniciado nesta sessão.")
    else: st.caption("Monitoramento não está ativo nesta sessão.")
    if st.button("Parar monitoramento"):
        if st.session_state.monitor_event is not None: st.session_state.monitor_event.set()
        st.session_state.monitor_running=False; st.success("Solicitação para parar enviada.")
    st.caption("A variação é calculada com os últimos fechamentos diários disponíveis no Yahoo Finance, não é cotação em tempo real. Alertas são informativos.")

elif page=="Registros":
    st.subheader("Histórico de e-mails e alertas")
    if st.session_state.logs:
        df=pd.DataFrame(st.session_state.logs)
        st.dataframe(df.iloc[::-1],use_container_width=True,hide_index=True)
        st.download_button("Baixar CSV",df.to_csv(index=False).encode("utf-8-sig"),"nexus_registros.csv","text/csv")
        if st.button("Limpar registros"): st.session_state.logs=[]; st.rerun()
    else: st.info("Nenhum registro nesta sessão.")

elif page=="Sobre":
    st.subheader("Sobre o Nexus AI")
    st.markdown("""
- **Mercado:** cotações consultadas pelo Yahoo Finance via `yfinance`.
- **Análise técnica:** médias móveis, RSI, MACD e candles.
- **IA:** Groq API, configurada pela variável `GROQ_API_KEY`.
- **Alertas:** e-mail via SMTP Gmail e senha de aplicativo.

Este aplicativo é informativo e não constitui recomendação de compra ou venda. Cotações podem atrasar e o envio de e-mails depende do Gmail e da conexão.
""")

st.divider()
st.caption(f"Nexus AI • {datetime.now():%d/%m/%Y %H:%M:%S}")
