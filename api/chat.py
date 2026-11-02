import json, os
from http.server import BaseHTTPRequestHandler
import requests
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            key=os.environ.get("GROQ_API_KEY")
            if not key: raise ValueError("Adicione GROQ_API_KEY nas variáveis de ambiente do Vercel.")
            n=int(self.headers.get("Content-Length","0"))
            if n>30000: raise ValueError("Pedido muito grande.")
            body=json.loads(self.rfile.read(n) or b"{}")
            symbol=str(body.get("symbol","ativo selecionado"))[:30]
            context=json.dumps(body.get("marketContext",[])[-15:],ensure_ascii=False)[:8000]
            msgs=[{"role":"system","content":"Você é Nexus AI, assistente educacional de análise financeira. Responda em português brasileiro, explique indicadores, não prometa ganhos, não dê garantias e esclareça que não é aconselhamento financeiro. Ativo: "+symbol+". Dados recentes: "+context}]
            for m in body.get("messages",[])[-12:]:
                if m.get("role") in ("user","assistant"): msgs.append({"role":m["role"],"content":str(m.get("content",""))[:4000]})
            r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":"Bearer "+key},json={"model":os.environ.get("GROQ_MODEL","llama-3.3-70b-versatile"),"messages":msgs,"temperature":0.3,"max_tokens":1200},timeout=25)
            if r.status_code>=400: raise ValueError("Erro na API Groq. Confira a chave, o modelo e os limites da conta.")
            out={"answer":r.json()["choices"][0]["message"]["content"]}; code=200
        except Exception as e: out={"error":str(e)}; code=500
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.end_headers(); self.wfile.write(json.dumps(out,ensure_ascii=False).encode())
