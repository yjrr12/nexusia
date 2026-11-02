
import os
import sys
import json
import time
import logging
import smtplib
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage

import yfinance as yf
from dotenv import load_dotenv

# =========================================================
# CONFIGURAÇÃO
# =========================================================

PASTA = Path(__file__).resolve().parent
load_dotenv(PASTA / ".env")

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "").strip()
EMAIL_SENHA_APP = os.getenv("EMAIL_SENHA_APP", "").replace(" ", "")
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO", "").strip()

LIMITE_VARIACAO = 5.0
INTERVALO_SEGUNDOS = 300
TIMEOUT_EMAIL = 30

ARQUIVO_ALERTAS = PASTA / "alertas_enviados.json"
ARQUIVO_LOG = PASTA / "monitor.log"

# Ações brasileiras, ETFs e índices americanos, criptomoedas.
# Adicione ou remova ativos neste dicionário.
ATIVOS = {
    # Brasil
    "PETR4.SA": "Petrobras PN",
    "VALE3.SA": "Vale",
    "ITUB4.SA": "Itaú Unibanco",
    "BBDC4.SA": "Bradesco PN",
    "BOVA11.SA": "ETF BOVA11",
    "^BVSP": "Ibovespa",

    # Estados Unidos
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
    "^DJI": "Dow Jones",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",

    # Criptomoedas
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
}

logging.basicConfig(
    filename=str(ARQUIVO_LOG),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

# =========================================================
# HISTÓRICO DOS ALERTAS
# =========================================================

def carregar_alertas():
    if not ARQUIVO_ALERTAS.exists():
        return {}

    try:
        with open(ARQUIVO_ALERTAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
            return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError):
        logging.exception("Falha ao ler o histórico de alertas.")
        return {}


def salvar_alertas(alertas):
    temporario = ARQUIVO_ALERTAS.with_suffix(".tmp")

    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(alertas, arquivo, ensure_ascii=False, indent=2)

    temporario.replace(ARQUIVO_ALERTAS)


# =========================================================
# E-MAIL
# =========================================================

def enviar_email(assunto, mensagem):
    if not EMAIL_REMETENTE or not EMAIL_SENHA_APP or not EMAIL_DESTINO:
        raise ValueError(
            "Preencha EMAIL_REMETENTE, EMAIL_SENHA_APP e "
            "EMAIL_DESTINO no arquivo .env."
        )

    email = EmailMessage()
    email["Subject"] = assunto
    email["From"] = EMAIL_REMETENTE
    email["To"] = EMAIL_DESTINO
    email.set_content(mensagem)

    with smtplib.SMTP(
        "smtp.gmail.com", 587, timeout=TIMEOUT_EMAIL
    ) as servidor:
        servidor.ehlo()
        servidor.starttls()
        servidor.ehlo()
        servidor.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
        servidor.send_message(email)


def testar_email():
    enviar_email(
        "Nexus AI - Teste de e-mail",
        "O envio de e-mails do monitor Nexus AI está funcionando.\n\n"
        "Este é apenas um teste de configuração.",
    )
    print("E-mail de teste enviado. Verifique sua caixa de entrada.")


# =========================================================
# COTAÇÕES E VARIAÇÃO DIÁRIA
# =========================================================

def obter_cotacao_e_variacao(ticker):
    ativo = yf.Ticker(ticker)

    # Cotações intradiárias: dados de 5 minutos disponíveis na fonte.
    intradia = ativo.history(
        period="2d",
        interval="5m",
        auto_adjust=False,
        prepost=False,
    )

    intradia = intradia.dropna(subset=["Close"])

    # Fechamentos diários usados para localizar o fechamento anterior.
    diario = ativo.history(
        period="10d",
        interval="1d",
        auto_adjust=False,
        prepost=False,
    )

    diario = diario.dropna(subset=["Close"])

    if intradia.empty or diario.empty:
        raise ValueError("A fonte não retornou dados suficientes.")

    preco_atual = float(intradia["Close"].iloc[-1])
    data_intradia = intradia.index[-1].date()

    # Se a barra intradiária pertence à sessão mais recente,
    # o fechamento anterior é a barra diária anterior.
    datas_diarias = [indice.date() for indice in diario.index]
    indices_mesma_data = [
        i for i, data in enumerate(datas_diarias)
        if data == data_intradia
    ]

    if indices_mesma_data:
        indice_atual = indices_mesma_data[-1]
        if indice_atual == 0:
            raise ValueError("Ainda não há fechamento anterior disponível.")
        fechamento_anterior = float(
            diario["Close"].iloc[indice_atual - 1]
        )
    else:
        # Se não há barra diária para a sessão intradiária mais recente,
        # usa o fechamento diário mais recente disponível.
        fechamento_anterior = float(diario["Close"].iloc[-1])

    if fechamento_anterior <= 0:
        raise ValueError("Fechamento anterior inválido.")

    variacao = (
        (preco_atual - fechamento_anterior) / fechamento_anterior
    ) * 100.0

    horario_dado = intradia.index[-1].strftime("%Y-%m-%d %H:%M:%S %Z")

    return preco_atual, fechamento_anterior, variacao, horario_dado


# =========================================================
# MONITORAMENTO
# =========================================================

def verificar_ativo(ticker, nome, alertas):
    try:
        preco, fechamento, variacao, horario = (
            obter_cotacao_e_variacao(ticker)
        )

        print(
            f"{ticker}: preço={preco:.4f} | "
            f"variação diária={variacao:+.2f}%"
        )

        if variacao >= LIMITE_VARIACAO:
            direcao = "SUBIDA"
        elif variacao <= -LIMITE_VARIACAO:
            direcao = "QUEDA"
        else:
            return

        # Uma notificação por ativo, direção e data de cotação.
        data_referencia = horario[:10]
        chave = f"{ticker}|{data_referencia}|{direcao}"

        if chave in alertas:
            logging.info("Alerta já enviado: %s", chave)
            return

        simbolo = "📈" if direcao == "SUBIDA" else "📉"
        assunto = f"{simbolo} Nexus AI: {direcao} de {nome}"

        mensagem = (
            "O monitor Nexus AI detectou uma variação diária relevante.\n\n"
            f"Ativo: {nome}\n"
            f"Símbolo: {ticker}\n"
            f"Último preço recebido: {preco:.6f}\n"
            f"Fechamento anterior: {fechamento:.6f}\n"
            f"Variação calculada: {variacao:+.2f}%\n"
            f"Limite configurado: +/-{LIMITE_VARIACAO:.2f}%\n"
            f"Horário da última barra recebida: {horario}\n\n"
            "Fonte: Yahoo Finance, por meio da biblioteca yfinance.\n"
            "A cotação pode estar atrasada ou incompleta. Confirme os "
            "dados diretamente na plataforma financeira antes de agir.\n"
            "Este alerta é informativo, não uma recomendação de investimento."
        )

        enviar_email(assunto, mensagem)

        # Só registra depois que o envio do e-mail foi concluído.
        alertas[chave] = datetime.now().isoformat(timespec="seconds")
        salvar_alertas(alertas)

        logging.info(
            "E-mail enviado: %s | %s | %.2f%%",
            ticker, direcao, variacao
        )
        print(f"*** ALERTA ENVIADO: {nome} ({variacao:+.2f}%) ***")

    except Exception as erro:
        logging.exception("Falha ao consultar %s", ticker)
        print(f"Erro em {ticker}: {erro}")


def main():
    print("=" * 55)
    print("NEXUS AI - MONITOR DE MERCADO")
    print("=" * 55)
    print(f"Ativos monitorados: {len(ATIVOS)}")
    print(f"Limite diário: +/-{LIMITE_VARIACAO}%")
    print(f"Consulta: a cada {INTERVALO_SEGUNDOS // 60} minutos")
    print("Para encerrar, pressione Ctrl+C.")
    print(f"Log: {ARQUIVO_LOG}")
    print()

    alertas = carregar_alertas()

    while True:
        inicio = time.monotonic()
        print(f"\nVerificação iniciada: {datetime.now():%d/%m/%Y %H:%M:%S}")

        for ticker, nome in ATIVOS.items():
            verificar_ativo(ticker, nome, alertas)
            time.sleep(1)

        duracao = time.monotonic() - inicio
        espera = max(1, INTERVALO_SEGUNDOS - duracao)

        print(
            f"Verificação concluída. Próxima rodada em "
            f"aproximadamente {espera:.0f} segundos."
        )
        time.sleep(espera)


if __name__ == "__main__":
    try:
        if "--test-email" in sys.argv:
            testar_email()
        else:
            main()
    except KeyboardInterrupt:
        print("\nMonitor encerrado pelo usuário.")
    except Exception as erro:
        logging.exception("Erro fatal no monitor.")
        print(f"Erro fatal: {erro}")
        sys.exit(1)
