"use client";

import { useCallback, useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid, ResponsiveContainer
} from "recharts";

type Point = {
  date: string;
  close: number;
  sma20: number | null;
  sma50: number | null;
  ema20: number | null;
  rsi: number | null;
  macd: number | null;
  macdSignal: number | null;
};

type Market = {
  ticker: string;
  price: number;
  change: number;
  data: Point[];
};

type Message = {
  role: "user" | "assistant";
  content: string;
};

const assets = [
  "PETR4.SA", "VALE3.SA", "ITUB4.SA",
  "BOVA11.SA", "AAPL", "MSFT", "NVDA",
  "GOOGL", "AMZN", "TSLA",
  "BTC-USD", "ETH-USD", "EURUSD=X",
  "BRL=X", "^BVSP", "^GSPC", "^IXIC"
];

const nav = [
  "Mercado",
  "Análise técnica",
  "Nexus AI",
  "E-mail e alertas",
  "Registros",
  "Sobre"
];

export default function Home() {
  const [tab, setTab] = useState("Mercado");
  const [ticker, setTicker] = useState("PETR4.SA");
  const [period, setPeriod] = useState("6mo");
  const [market, setMarket] = useState<Market | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);

  const [sender, setSender] = useState("");
  const [password, setPassword] = useState("");
  const [recipient, setRecipient] = useState("");

  const [logs, setLogs] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `/api/market?ticker=${encodeURIComponent(ticker)}&period=${period}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro ao carregar mercado.");
      }

      setMarket(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro desconhecido.");
      setMarket(null);
    } finally {
      setLoading(false);
    }
  }, [ticker, period]);

  useEffect(() => {
    void load();
  }, [load]);

  async function sendMessage() {
    if (!prompt.trim() || busy) return;

    const next: Message[] = [
      ...messages,
      { role: "user", content: prompt }
    ];

    setMessages(next);
    setPrompt("");
    setBusy(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ messages: next })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro no Groq.");
      }

      setMessages([
        ...next,
        { role: "assistant", content: data.answer }
      ]);
    } catch (e) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Erro."
        }
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function testEmail() {
    const response = await fetch("/api/email", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        sender,
        password,
        recipient
      })
    });

    const data = await response.json();

    alert(data.message || data.error);

    setLogs(old => [
      `${new Date().toLocaleString("pt-BR")} — ${data.message || data.error}`,
      ...old
    ]);
  }

  function exportLogs() {
    const content = logs.join("\n");
    const blob = new Blob([content], {
      type: "text/csv;charset=utf-8"
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = "nexus-registros.csv";
    a.click();

    URL.revokeObjectURL(url);
  }

  return (
    <main className="layout">
      <aside className="sidebar">
        <h2>NEXUS AI</h2>
        <p>MARKET INTELLIGENCE</p>

        {nav.map(item => (
          <button
            key={item}
            className={tab === item ? "selected" : ""}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}

        <small>Dados de mercado podem ter atraso.</small>
      </aside>

      <section className="content">
        <header>
          <div>
            <small>PAINEL DE CONTROLE</small>
            <h1>{tab}</h1>
          </div>

          <button onClick={() => void load()}>
            Atualizar
          </button>
        </header>

        {tab === "Mercado" && (
          <>
            <div className="panel">
              <h2>Acompanhe os mercados.</h2>
              <p>Escolha um ativo para consultar.</p>

              <div className="assets">
                {assets.map(asset => (
                  <button
                    key={asset}
                    onClick={() => {
                      setTicker(asset);
                      setTab("Análise técnica");
                    }}
                  >
                    {asset}
                  </button>
                ))}
              </div>
            </div>

            {market && (
              <div className="panel">
                <h2>{market.ticker}</h2>
                <h1>{market.price.toFixed(2)}</h1>
                <strong>{market.change.toFixed(2)}%</strong>
              </div>
            )}
          </>
        )}

        {tab === "Análise técnica" && (
          <>
            <div className="panel controls">
              <label>Ativo</label>
              <select
                value={ticker}
                onChange={e => setTicker(e.target.value)}
              >
                {assets.map(a => (
                  <option key={a}>{a}</option>
                ))}
              </select>

              <label>Período</label>
              <select
                value={period}
                onChange={e => setPeriod(e.target.value)}
              >
                {["1mo", "3mo", "6mo", "1y", "2y", "5y"].map(p => (
                  <option key={p}>{p}</option>
                ))}
              </select>

              <button onClick={() => void load()}>
                Buscar análise
              </button>
            </div>

            {loading && <p>Carregando...</p>}
            {error && <p className="error">{error}</p>}

            {market && (
              <>
                <div className="stats">
                  <div className="panel">
                    <small>Preço</small>
                    <h2>{market.price.toFixed(2)}</h2>
                  </div>

                  <div className="panel">
                    <small>Variação</small>
                    <h2>{market.change.toFixed(2)}%</h2>
                  </div>

                  <div className="panel">
                    <small>RSI 14</small>
                    <h2>{market.data.at(-1)?.rsi?.toFixed(2) ?? "N/D"}</h2>
                  </div>

                  <div className="panel">
                    <small>MACD</small>
                    <h2>{market.data.at(-1)?.macd?.toFixed(2) ?? "N/D"}</h2>
                  </div>
                </div>

                <div className="panel">
                  <h3>Preço e médias móveis</h3>

                  <div style={{ width: "100%", height: 350 }}>
                    <ResponsiveContainer>
                      <LineChart data={market.data}>
                        <CartesianGrid stroke="#26364d" />
                        <XAxis dataKey="date" />
                        <YAxis domain={["auto", "auto"]} />
                        <Tooltip />

                        <Line
                          dataKey="close"
                          name="Fechamento"
                          stroke="#62a8ff"
                          dot={false}
                        />

                        <Line
                          dataKey="sma20"
                          name="SMA 20"
                          stroke="#f0b65d"
                          dot={false}
                        />

                        <Line
                          dataKey="sma50"
                          name="SMA 50"
                          stroke="#c38bff"
                          dot={false}
                        />

                        <Line
                          dataKey="ema20"
                          name="EMA 20"
                          stroke="#58d6b0"
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="panel">
                  <h3>RSI</h3>
                  <div style={{ width: "100%", height: 220 }}>
                    <ResponsiveContainer>
                      <LineChart data={market.data}>
                        <CartesianGrid stroke="#26364d" />
                        <XAxis dataKey="date" hide />
                        <YAxis domain={[0, 100]} />
                        <Tooltip />
                        <Line dataKey="rsi" stroke="#58d6b0" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="panel">
                  <h3>MACD</h3>
                  <div style={{ width: "100%", height: 220 }}>
                    <ResponsiveContainer>
                      <LineChart data={market.data}>
                        <CartesianGrid stroke="#26364d" />
                        <XAxis dataKey="date" hide />
                        <YAxis />
                        <Tooltip />
                        <Line dataKey="macd" stroke="#62a8ff" dot={false} />
                        <Line dataKey="macdSignal" stroke="#f0b65d" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {tab === "Nexus AI" && (
          <div className="panel">
            <h2>Assistente Nexus AI</h2>

            <div className="messages">
              {messages.map((m, i) => (
                <div className="message" key={i}>
                  <b>{m.role === "user" ? "Você" : "Nexus AI"}</b>
                  <p>{m.content}</p>
                </div>
              ))}
            </div>

            <div className="chat">
              <input
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter") void sendMessage();
                }}
                placeholder="Digite sua pergunta..."
              />

              <button disabled={busy} onClick={() => void sendMessage()}>
                {busy ? "..." : "Enviar"}
              </button>
            </div>

            <button className="secondary" onClick={() => setMessages([])}>
              Limpar conversa
            </button>
          </div>
        )}

        {tab === "E-mail e alertas" && (
          <div className="panel">
            <h2>Configuração de e-mail</h2>

            <label>Gmail remetente</label>
            <input value={sender} onChange={e => setSender(e.target.value)} />

            <label>Senha de aplicativo Gmail</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />

            <label>Destinatário</label>
            <input value={recipient} onChange={e => setRecipient(e.target.value)} />

            <button onClick={() => void testEmail()}>
              Testar envio de e-mail
            </button>

            <p className="note">
              O monitoramento automático desta versão só funciona enquanto
              a página estiver aberta. Não é um serviço 24 horas.
            </p>
          </div>
        )}

        {tab === "Registros" && (
          <div className="panel">
            <h2>Registros</h2>

            {logs.map((log, i) => (
              <p key={i}>{log}</p>
            ))}

            <button onClick={exportLogs}>
              Exportar CSV
            </button>

            <button className="secondary" onClick={() => setLogs([])}>
              Limpar registros
            </button>
          </div>
        )}

        {tab === "Sobre" && (
          <div className="panel">
            <h2>Nexus AI</h2>
            <p>
              Plataforma informativa de mercado com análise técnica,
              gráficos e assistente de IA.
            </p>
            <p>
              Indicadores históricos não garantem resultados futuros.
              Este aplicativo não constitui recomendação de compra ou venda.
            </p>
          </div>
        )}

        <footer>NEXUS AI · MARKET INTELLIGENCE</footer>
      </section>
    </main>
  );
}