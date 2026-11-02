import json
import smtplib
import ssl

from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):

    def do_POST(self):

        try:
            length = int(
                self.headers.get("Content-Length", "0")
            )

            data = json.loads(
                self.rfile.read(length) or b"{}"
            )

            sender = data.get("sender", "").strip()
            password = data.get("password", "").replace(" ", "")
            recipient = data.get("recipient", "").strip()

            if not sender or not password or not recipient:
                self.reply(400, {
                    "error": "Preencha os campos de e-mail."
                })
                return

            message = EmailMessage()

            message["From"] = sender
            message["To"] = recipient
            message["Subject"] = "Nexus AI - Teste"

            message.set_content(
                "Seu sistema Nexus AI está funcionando."
            )

            context = ssl.create_default_context()

            with smtplib.SMTP_SSL(
                "smtp.gmail.com",
                465,
                timeout=20,
                context=context
            ) as smtp:

                smtp.login(sender, password)
                smtp.send_message(message)

            self.reply(200, {
                "ok": True,
                "message": "E-mail enviado."
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