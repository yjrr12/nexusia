import json
import os
import urllib.request
import urllib.error

from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):

    def do_POST(self):

        try:
            api_key = os.environ.get("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")

            if not api_key:
                self.reply(500, {
                    "error": "Configure GROQ_API_KEY na Vercel."
                })
                return

            length = int(
                self.headers.get("Content-Length", "0")
            )

            data = json.loads(
                self.rfile.read(length) or b"{}"
            )

            messages = data.get("messages", [])

            if not isinstance(messages, list) or not messages:
                self.reply(400, {
                    "error": "Conversa vazia."
                })
                return

            messages = [
                {
                    "role": message.get("role"),
                    "content": str(message.get("content", ""))[:12000]
                }
                for message in messages[-18:]
                if message.get("role") in [
                    "user", "assistant", "system"
                ]
            ]

            if not any(m["role"] == "system" for m in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": (
                        "Você é o Nexus AI. "
                        "Responda em português brasileiro. "
                        "Explique conceitos de mercado e riscos. "
                        "Não prometa lucros nem apresente "
                        "informações como recomendações personalizadas."
                    )
                })

            payload = json.dumps({
                "model": os.environ.get(
                    "GROQ_MODEL",
                    "llama-3.3-70b-versatile"
                ),
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 1200
            }).encode()

            request = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=25
            ) as response:

                result = json.loads(response.read())

            answer = result["choices"][0]["message"]["content"]

            self.reply(200, {"answer": answer})

        except urllib.error.HTTPError as e:
            detail = e.read().decode(
                "utf-8", "replace"
            )[:500]

            self.reply(502, {
                "error": "Erro do Groq: " + detail
            })

        except Exception as e:
            self.reply(500, {
                "error": str(e)
            })

    def reply(self, status, data):

        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode()

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.end_headers()
        self.wfile.write(body)