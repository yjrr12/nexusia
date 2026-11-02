
import streamlit as st
import streamlit_autorefresh
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import smtplib
import json
import os
import threading
import time
import csv
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# CONFIGURAÇÃO
# =========================================================

st.set_page_config(
    page_title="Nexus AI",
    page_icon="📈",
    layout="wide"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "claude-trading-skills")
LOG_FILE = os.path.join(BASE_DIR, "nexus_alertas.csv")
CONFIG_FILE = os.path.join(BASE_DIR, "nexus_config.json")

if "email_config" not in st.session_state:
    st.session_state.email_config = {
        "sender": "",
        "password": "",
        "receiver": "",
        "smtp": "smtp.gmail.com",
        "port": 587
    }

if "monitor_running" not in st.session_state:
    st.session_state.monitor_running = False

if "alerts" not in st.session_state:
    st.session_state.alerts = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =========================================================
# MERCADOS E ATIVOS POPULARES
# =========================================================

MARKETS = {
    "Brasil": {
        "Ibovespa": "^BVSP",
        "Petrobras PN": "PETR4.SA",
        "Petrobras ON": "PETR3.SA",
        "Vale": "VALE3.SA",
        "Itaú": "ITUB4.SA",
        "Banco do Brasil": "BBAS3.SA",
        "B3": "B3SA3.SA",
        "WEG": "WEGE3.SA",
        "Ambev": "ABEV3.SA",
        "Magazine Luiza": "MGLU3.SA",
        "Bradesco": "BBDC4.SA"
    },
    "Estados Unidos": {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Dow Jones": "^DJI",
        "Russell 2000": "^RUT",
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Nvidia": "NVDA",
        "Amazon": "AMZN",
        "Google": "GOOGL",
        "Tesla": "TSLA",
        "Meta": "META",
        "AMD": "AMD",
        "Intel": "INTC",
        "Coca-Cola": "KO"
    },
    "Europa": {
        "DAX Alemanha": "^GDAXI",
        "FTSE 100 Reino Unido": "^FTSE",
        "CAC 40 França": "^FCHI",
        "Euro Stoxx 50": "^STOXX50E",
        "AEX Holanda": "^AEX",
        "FTSE MIB Itália": "FTSEMIB.MI",
        "IBEX 35 Espanha": "^IBEX",
        "SMI Suíça": "^SSMI",
        "SAP": "SAP",
        "ASML": "ASML",
        "Siemens": "SIE.DE",
        "LVMH": "MC.PA",
        "Shell": "SHEL"
    },
    "Ásia": {
        "Nikkei 225 Japão": "^N225",
        "Hang Seng Hong Kong": "^HSI",
        "Shanghai Composite": "000001.SS",
        "Kospi Coreia do Sul": "^KS11",
        "Taiwan Weighted": "^TWII",
        "Toyota": "7203.T",
        "Sony": "6758.T",
        "Alibaba": "BABA",
        "Tencent": "0700.HK",
        "Samsung": "005930.KS",
        "TSMC": "TSM"
    },
    "Criptomoedas": {
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        "Solana": "SOL-USD",
        "XRP": "XRP-USD",
        "Dogecoin": "DOGE-USD"
    },
    "Câmbio": {
        "EUR/USD": "EURUSD=X",
        "USD/BRL": "BRL=X",
        "EUR/BRL": "EURBRL=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "USD/CNY": "CNY=X",
        "USD/CHF": "CHF=X",
        "USD/CAD": "CAD=X",
        "AUD/USD": "AUDUSD=X",
        "NZD/USD": "NZDUSD=X",
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "GBP/JPY": "GBPJPY=X",
        "USD/INR": "INR=X",
        "USD/MXN": "MXN=X",
        "USD/ZAR": "ZAR=X",
        "USD/KRW": "KRW=X",
        "USD/SGD": "SGD=X",
        "USD/HKD": "HKD=X"
    }
}

# =========================================================
# DADOS DE MERCADO
# =========================================================

@st.cache_data(ttl=240)
def obter_historico(ticker, intervalo, periodo):
    try:
        dados = yf.Ticker(ticker).history(
            period=periodo,
            interval=intervalo,
            auto_adjust=True
        )
        if dados is None or dados.empty:
            return pd.DataFrame()
        return dados.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=240)
def obter_resumo(ticker):
    try:
        dados = yf.Ticker(ticker).history(period="5d", interval="1d")
        if dados.empty:
            return None

        fechamento = float(dados["Close"].iloc[-1])
        anterior = (
            float(dados["Close"].iloc[-2])
            if len(dados) > 1
            else fechamento
        )

        variacao = (
            ((fechamento - anterior) / anterior) * 100
            if anterior
            else 0
        )

        return {
            "preco": fechamento,
            "variacao": variacao
        }
    except Exception:
        return None


def pesquisar_ativos(consulta):
    consulta = consulta.strip()
    if not consulta:
        return []

    resultados = []

    # Procura primeiro nos ativos cadastrados.
    for categoria, ativos in MARKETS.items():
        for nome, ticker in ativos.items():
            if (
                consulta.lower() in nome.lower()
                or consulta.lower() in ticker.lower()
            ):
                resultados.append({
                    "nome": nome,
                    "ticker": ticker,
                    "categoria": categoria
                })

    # Depois tenta a busca online do Yahoo Finance.
    try:
        busca = yf.Search(consulta, max_results=10)
        for item in busca.quotes:
            ticker = item.get("symbol")
            nome = (
                item.get("shortname")
                or item.get("longname")
                or ticker
            )

            if ticker and not any(
                ativo["ticker"] == ticker for ativo in resultados
            ):
                resultados.append({
                    "nome": nome,
                    "ticker": ticker,
                    "categoria": item.get("quoteType", "Outro")
                })
    except Exception:
        pass

    # Permite informar diretamente um ticker.
    if not resultados and any(c in consulta for c in ".^=-"):
        resultados.append({
            "nome": consulta.upper(),
            "ticker": consulta.upper(),
            "categoria": "Ticker digitado"
        })

    return resultados[:30]


# =========================================================
# INDICADORES TÉCNICOS
# =========================================================

def calcular_indicadores(dados):
    if dados.empty:
        return dados

    dados = dados.copy()

    dados["SMA20"] = dados["Close"].rolling(20).mean()
    dados["SMA50"] = dados["Close"].rolling(50).mean()
    dados["EMA9"] = dados["Close"].ewm(span=9, adjust=False).mean()
    dados["EMA21"] = dados["Close"].ewm(span=21, adjust=False).mean()

    delta = dados["Close"].diff()
    ganhos = delta.clip(lower=0)
    perdas = -delta.clip(upper=0)

    media_ganhos = ganhos.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    media_perdas = perdas.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    rs = media_ganhos / media_perdas.replace(0, float("nan"))
    dados["RSI"] = 100 - (100 / (1 + rs))

    ema12 = dados["Close"].ewm(span=12, adjust=False).mean()
    ema26 = dados["Close"].ewm(span=26, adjust=False).mean()

    dados["MACD"] = ema12 - ema26
    dados["MACD_Sinal"] = dados["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    dados["MACD_Hist"] = dados["MACD"] - dados["MACD_Sinal"]

    return dados


def gerar_analise(dados):
    if dados.empty or len(dados) < 2:
        return "Dados insuficientes para analisar este ativo."

    ultimo = dados.iloc[-1]
    anterior = dados.iloc[-2]

    mensagens = []

    if pd.notna(ultimo.get("RSI")):
        rsi = float(ultimo["RSI"])
        if rsi >= 70:
            mensagens.append("RSI indica possível sobrecompra.")
        elif rsi <= 30:
            mensagens.append("RSI indica possível sobrevenda.")
        else:
            mensagens.append(f"RSI em {rsi:.2f}, dentro da faixa intermediária.")

    if pd.notna(ultimo.get("EMA9")) and pd.notna(ultimo.get("EMA21")):
        if ultimo["EMA9"] > ultimo["EMA21"]:
            mensagens.append("EMA 9 acima da EMA 21: sinal de tendência positiva.")
        else:
            mensagens.append("EMA 9 abaixo da EMA 21: sinal de tendência negativa.")

    if pd.notna(ultimo.get("MACD")) and pd.notna(ultimo.get("MACD_Sinal")):
        if ultimo["MACD"] > ultimo["MACD_Sinal"]:
            mensagens.append("MACD acima da linha de sinal.")
        else:
            mensagens.append("MACD abaixo da linha de sinal.")

    if ultimo["Close"] > anterior["Close"]:
        mensagens.append("O último fechamento subiu em relação ao candle anterior.")
    elif ultimo["Close"] < anterior["Close"]:
        mensagens.append("O último fechamento caiu em relação ao candle anterior.")

    return "\n\n".join(mensagens) or "Sem sinais suficientes."


# =========================================================
# GRÁFICOS
# =========================================================

def mostrar_grafico(dados, ticker, mostrar_indicadores=True):
    if dados.empty:
        st.warning("Não há dados disponíveis para este ativo e intervalo.")
        return

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=dados.index,
        open=dados["Open"],
        high=dados["High"],
        low=dados["Low"],
        close=dados["Close"],
        name=ticker
    ))

    if mostrar_indicadores:
        for coluna, nome in [
            ("SMA20", "SMA 20"),
            ("SMA50", "SMA 50"),
            ("EMA9", "EMA 9"),
            ("EMA21", "EMA 21")
        ]:
            if coluna in dados.columns:
                fig.add_trace(go.Scatter(
                    x=dados.index,
                    y=dados[coluna],
                    name=nome,
                    mode="lines"
                ))

    fig.update_layout(
        title=f"{ticker} — gráfico de preços",
        xaxis_title="Data e hora",
        yaxis_title="Preço",
        xaxis_rangeslider_visible=False,
        height=600,
        template="plotly_dark",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)


def mostrar_indicadores(dados):
    if dados.empty:
        return

    if "RSI" in dados.columns:
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(
            x=dados.index,
            y=dados["RSI"],
            name="RSI"
        ))
        fig_rsi.add_hline(y=70, line_dash="dash")
        fig_rsi.add_hline(y=30, line_dash="dash")
        fig_rsi.update_layout(
            title="RSI — Índice de Força Relativa",
            height=300,
            template="plotly_dark"
        )
        st.plotly_chart(fig_rsi, use_container_width=True)

    if "MACD" in dados.columns:
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(
            x=dados.index,
            y=dados["MACD"],
            name="MACD"
        ))
        fig_macd.add_trace(go.Scatter(
            x=dados.index,
            y=dados["MACD_Sinal"],
            name="Sinal"
        ))
        fig_macd.add_trace(go.Bar(
            x=dados.index,
            y=dados["MACD_Hist"],
            name="Histograma"
        ))
        fig_macd.update_layout(
            title="MACD",
            height=350,
            template="plotly_dark"
        )
        st.plotly_chart(fig_macd, use_container_width=True)


# =========================================================
# OLLAMA
# =========================================================

def consultar_ollama(pergunta, modelo="qwen2.5:7b"):
    try:
        resposta = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": modelo,
                "messages": [{"role": "user", "content": pergunta}],
                "stream": False
            },
            timeout=120
        )
        resposta.raise_for_status()
        return resposta.json()["message"]["content"]
    except Exception as erro:
        return (
            "Não foi possível acessar o Ollama. Confira se ele está "
            f"executando e se o modelo {modelo} está instalado.\n\nErro: {erro}"
        )


# =========================================================
# SKILLS LOCAIS
# =========================================================

def carregar_skills():
    encontrados = []

    if not os.path.isdir(SKILLS_DIR):
        return encontrados

    for raiz, _, arquivos in os.walk(SKILLS_DIR):
        for arquivo in arquivos:
            if arquivo.lower() == "skill.md":
                caminho = os.path.join(raiz, arquivo)
                try:
                    with open(caminho, "r", encoding="utf-8") as f:
                        encontrados.append({
                            "nome": os.path.relpath(caminho, SKILLS_DIR),
                            "conteudo": f.read()
                        })
                except Exception:
                    pass

    return encontrados


# =========================================================
# ALERTAS POR E-MAIL
# =========================================================

def enviar_email(config, assunto, corpo):
    if not config["sender"] or not config["receiver"] or not config["password"]:
        raise ValueError("Preencha remetente, senha de app e destinatário.")

    mensagem = MIMEMultipart()
    mensagem["From"] = config["sender"]
    mensagem["To"] = config["receiver"]
    mensagem["Subject"] = assunto
    mensagem.attach(MIMEText(corpo, "plain", "utf-8"))

    with smtplib.SMTP(config["smtp"], int(config["port"])) as servidor:
        servidor.starttls()
        servidor.login(config["sender"], config["password"])
        servidor.send_message(mensagem)


def registrar_alerta(ticker, preco, variacao, motivo):
    registro = {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ticker": ticker,
        "preco": preco,
        "variacao_percentual": variacao,
        "motivo": motivo
    }

    novo = not os.path.exists(LOG_FILE)

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=registro.keys())
        if novo:
            escritor.writeheader()
        escritor.writerow(registro)


# =========================================================
# INTERFACE
# =========================================================

st.title("📈 Nexus AI")
st.caption("Mercados globais, análise técnica e monitoramento de ativos")

with st.sidebar:
    st.header("⚙️ Configurações")

    frequencia = st.selectbox(
        "Atualização automática",
        ["A cada 5 minutos", "A cada 1 hora"]
    )

    intervalo_refresh = (
        5 * 60 * 1000
        if frequencia == "A cada 5 minutos"
        else 60 * 60 * 1000
    )

    st_autorefresh = streamlit_autorefresh.st_autorefresh
    st_autorefresh(
        interval=intervalo_refresh,
        key="nexus_auto_refresh"
    )

    if st.button("🔄 Atualizar dados agora", use_container_width=True):
        obter_historico.clear()
        obter_resumo.clear()
        st.rerun()

    st.divider()
    pagina = st.radio(
        "Navegação",
        [
            "Mercado",
            "Análise Técnica",
            "Nexus AI",
            "Alertas por e-mail",
            "Skills",
            "Registros",
            "Sobre"
        ]
    )

    st.caption(f"Última atualização da interface: {datetime.now():%H:%M:%S}")

# =========================================================
# PESQUISA COMPARTILHADA
# =========================================================

def seletor_pesquisa(chave):
    consulta = st.text_input(
        "🔎 Pesquisar ativo por nome ou ticker",
        placeholder="Ex.: Petrobras, AAPL, EURUSD=X, BTC-USD",
        key=f"consulta_{chave}"
    )

    resultados = pesquisar_ativos(consulta) if consulta else []

    if resultados:
        opcoes = {
            f"{item['nome']} ({item['ticker']}) — {item['categoria']}":
            item["ticker"]
            for item in resultados
        }

        escolhido = st.selectbox(
            "Resultados da pesquisa",
            list(opcoes.keys()),
            key=f"escolha_{chave}"
        )
        return opcoes[escolhido]

    categoria = st.selectbox(
        "Ou selecione um mercado",
        list(MARKETS.keys()),
        key=f"categoria_{chave}"
    )

    nomes = MARKETS[categoria]
    nome = st.selectbox(
        "Ativo",
        list(nomes.keys()),
        key=f"ativo_{chave}"
    )

    return nomes[nome]


def controles_periodo(chave):
    escolha = st.selectbox(
        "Intervalo dos candles",
        [
            "5 minutos",
            "15 minutos",
            "30 minutos",
            "1 hora",
            "1 dia"
        ],
        index=3,
        key=f"periodo_{chave}"
    )

    mapa = {
        "5 minutos": ("5m", "5d"),
        "15 minutos": ("15m", "1mo"),
        "30 minutos": ("30m", "1mo"),
        "1 hora": ("60m", "1mo"),
        "1 dia": ("1d", "1y")
    }

    return mapa[escolha]


# =========================================================
# PÁGINA: MERCADO
# =========================================================

if pagina == "Mercado":
    st.header("🌎 Mercado global")

    ticker = seletor_pesquisa("mercado")
    intervalo, periodo = controles_periodo("mercado")

    dados = obter_historico(ticker, intervalo, periodo)

    if not dados.empty:
        fechamento = float(dados["Close"].iloc[-1])
        primeiro = float(dados["Close"].iloc[0])
        variacao = ((fechamento - primeiro) / primeiro * 100) if primeiro else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Último preço", f"{fechamento:,.4f}")
        c2.metric("Variação do período", f"{variacao:.2f}%")
        c3.metric("Candles recebidos", len(dados))

        dados_indicadores = calcular_indicadores(dados)
        mostrar_grafico(dados_indicadores, ticker)

        st.subheader("Últimos registros")
        st.dataframe(
            dados.tail(20).sort_index(ascending=False),
            use_container_width=True
        )
    else:
        st.warning(
            "Não foi possível obter dados. Tente outro ticker ou intervalo."
        )

    st.divider()
    st.subheader("🌐 Visão geral de ativos")

    categoria_resumo = st.selectbox(
        "Mercado para visualizar",
        list(MARKETS.keys()),
        key="resumo_categoria"
    )

    linhas = []
    barra = st.progress(0)

    ativos = list(MARKETS[categoria_resumo].items())

    for i, (nome, codigo) in enumerate(ativos):
        resumo = obter_resumo(codigo)
        if resumo:
            linhas.append({
                "Ativo": nome,
                "Ticker": codigo,
                "Preço": resumo["preco"],
                "Variação diária (%)": resumo["variacao"]
            })
        barra.progress((i + 1) / len(ativos))

    barra.empty()

    if linhas:
        st.dataframe(
            pd.DataFrame(linhas),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhum dado disponível para este mercado agora.")

# =========================================================
# PÁGINA: ANÁLISE TÉCNICA
# =========================================================

elif pagina == "Análise Técnica":
    st.header("📊 Análise técnica")

    ticker = seletor_pesquisa("analise")
    intervalo, periodo = controles_periodo("analise")

    dados = obter_historico(ticker, intervalo, periodo)

    if dados.empty:
        st.error("Não foi possível obter dados para esse ativo.")
    else:
        dados = calcular_indicadores(dados)

        c1, c2, c3 = st.columns(3)

        ultimo = dados.iloc[-1]

        c1.metric("Último preço", f"{ultimo['Close']:,.4f}")

        if pd.notna(ultimo.get("RSI")):
            c2.metric("RSI", f"{ultimo['RSI']:.2f}")
        else:
            c2.metric("RSI", "Calculando")

        if pd.notna(ultimo.get("MACD")):
            c3.metric("MACD", f"{ultimo['MACD']:.4f}")
        else:
            c3.metric("MACD", "Calculando")

        mostrar_grafico(dados, ticker)
        mostrar_indicadores(dados)

        st.subheader("🧠 Interpretação dos indicadores")
        st.write(gerar_analise(dados))

        st.warning(
            "Os indicadores são ferramentas informativas, não previsões "
            "garantidas nem recomendações de compra ou venda."
        )

        with st.expander("Ver tabela completa de indicadores"):
            colunas = [
                "Open", "High", "Low", "Close", "Volume",
                "SMA20", "SMA50", "EMA9", "EMA21",
                "RSI", "MACD", "MACD_Sinal", "MACD_Hist"
            ]
            colunas = [c for c in colunas if c in dados.columns]
            st.dataframe(
                dados[colunas].tail(100).sort_index(ascending=False),
                use_container_width=True
            )

# =========================================================
# PÁGINA: NEXUS AI
# =========================================================

elif pagina == "Nexus AI":
    st.header("🤖 Assistente de mercado local")

    modelo = st.selectbox(
        "Modelo Ollama",
        ["qwen2.5:7b", "llama3.1:8b", "mistral"]
    )

    for mensagem in st.session_state.chat_history:
        with st.chat_message(mensagem["role"]):
            st.markdown(mensagem["content"])

    pergunta = st.chat_input(
        "Pergunte sobre mercados, indicadores ou conceitos financeiros..."
    )

    if pergunta:
        st.session_state.chat_history.append({
            "role": "user",
            "content": pergunta
        })

        with st.chat_message("user"):
            st.markdown(pergunta)

        with st.chat_message("assistant"):
            with st.spinner("Consultando o modelo local..."):
                resposta = consultar_ollama(pergunta, modelo)
                st.markdown(resposta)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": resposta
        })

    if st.button("Limpar conversa"):
        st.session_state.chat_history = []
        st.rerun()

# =========================================================
# PÁGINA: ALERTAS POR E-MAIL
# =========================================================

elif pagina == "Alertas por e-mail":
    st.header("📧 Alertas por e-mail")

    st.info(
        "Configure o Gmail usando uma senha de app. Nunca use a senha "
        "normal da sua conta Google."
    )

    with st.form("form_email"):
        sender = st.text_input(
            "E-mail remetente",
            value=st.session_state.email_config["sender"]
        )
        password = st.text_input(
            "Senha de app do Gmail",
            type="password"
        )
        receiver = st.text_input(
            "E-mail destinatário",
            value=st.session_state.email_config["receiver"]
        )

        smtp = st.text_input(
            "Servidor SMTP",
            value=st.session_state.email_config["smtp"]
        )

        port = st.number_input(
            "Porta SMTP",
            min_value=1,
            max_value=65535,
            value=587
        )

        salvar = st.form_submit_button("Salvar configuração")

    if salvar:
        st.session_state.email_config = {
            "sender": sender,
            "password": password,
            "receiver": receiver,
            "smtp": smtp,
            "port": int(port)
        }
        st.success("Configuração salva nesta sessão.")

    st.caption(
        "A configuração não é gravada em disco; será necessário "
        "preenchê-la novamente após reiniciar a aplicação."
    )

    if st.button("✉️ Testar e-mail"):
        try:
            enviar_email(
                st.session_state.email_config,
                "Teste Nexus AI",
                "Seu envio de e-mail do Nexus AI está funcionando."
            )
            st.success("E-mail enviado.")
        except Exception as erro:
            st.error(f"Falha no envio: {erro}")

    st.divider()
    st.subheader("Configurar alerta de preço")

    ticker_alerta = st.text_input(
        "Ticker para monitorar",
        value="PETR4.SA"
    )

    limite = st.number_input(
        "Variação para disparar alerta (%)",
        min_value=0.1,
        max_value=100.0,
        value=5.0,
        step=0.5
    )

    frequencia_alerta = st.selectbox(
        "Verificar alerta a cada",
        ["5 minutos", "1 hora"],
        key="freq_alerta"
    )

    if st.button("Verificar preço agora"):
        try:
            dados_alerta = yf.Ticker(ticker_alerta).history(
                period="5d", interval="1d"
            )

            if len(dados_alerta) >= 2:
                atual = float(dados_alerta["Close"].iloc[-1])
                anterior = float(dados_alerta["Close"].iloc[-2])
                variacao = (atual - anterior) / anterior * 100

                st.metric(
                    f"Variação diária de {ticker_alerta}",
                    f"{variacao:.2f}%"
                )

                if abs(variacao) >= limite:
                    st.warning("O limite configurado foi atingido.")
                    try:
                        enviar_email(
                            st.session_state.email_config,
                            f"Alerta Nexus AI: {ticker_alerta}",
                            f"Preço: {atual}\nVariação diária: {variacao:.2f}%"
                        )
                        registrar_alerta(
                            ticker_alerta,
                            atual,
                            variacao,
                            "Limite percentual atingido"
                        )
                        st.success("Alerta enviado por e-mail.")
                    except Exception as erro:
                        st.error(f"Não foi possível enviar o e-mail: {erro}")
            else:
                st.warning("Histórico insuficiente para calcular a variação.")
        except Exception as erro:
            st.error(f"Erro ao consultar ativo: {erro}")

    st.caption(
        "Esta versão permite verificar alertas manualmente. O monitoramento "
        "automático em segundo plano contínuo ainda não está implementado."
    )

# =========================================================
# PÁGINA: SKILLS
# =========================================================

elif pagina == "Skills":
    st.header("🧩 Claude Trading Skills")

    skills = carregar_skills()

    if not skills:
        st.info(
            "Nenhum arquivo SKILL.md foi encontrado. Coloque a pasta "
            "'claude-trading-skills' ao lado do app.py."
        )
    else:
        nomes = [skill["nome"] for skill in skills]
        selecionada = st.selectbox("Selecionar skill", nomes)

        for skill in skills:
            if skill["nome"] == selecionada:
                st.markdown(skill["conteudo"])
                break

# =========================================================
# PÁGINA: REGISTROS
# =========================================================

elif pagina == "Registros":
    st.header("📋 Registros de alertas")

    if os.path.exists(LOG_FILE):
        try:
            registros = pd.read_csv(LOG_FILE)
            st.dataframe(registros, use_container_width=True)

            st.download_button(
                "⬇️ Baixar CSV",
                data=registros.to_csv(index=False).encode("utf-8"),
                file_name="nexus_alertas.csv",
                mime="text/csv"
            )
        except Exception as erro:
            st.error(f"Erro ao ler registros: {erro}")
    else:
        st.info("Nenhum alerta foi registrado ainda.")

# =========================================================
# PÁGINA: SOBRE
# =========================================================

elif pagina == "Sobre":
    st.header("ℹ️ Sobre o Nexus AI")

    st.markdown("""
    **Nexus AI** é um painel de acompanhamento de mercados.

    Recursos:
    - Busca de ativos por nome ou ticker.
    - Mercados do Brasil, Estados Unidos, Europa e Ásia.
    - Criptomoedas e pares cambiais.
    - Gráficos de candles de 5, 15 e 30 minutos, 1 hora e 1 dia.
    - Médias móveis, RSI e MACD.
    - Assistente com Ollama local.
    - Teste de alertas por e-mail.
    - Leitura de arquivos locais `SKILL.md`.

    **Limitações:**
    - Os dados vêm do Yahoo Finance e podem ter atraso, indisponibilidade
      ou limitações por ativo e intervalo.
    - Atualização automática da interface não garante atualização da bolsa
      nem dados em tempo real.
    - Os alertas desta versão são manuais.
    - Indicadores técnicos não garantem resultados financeiros.
    """)
