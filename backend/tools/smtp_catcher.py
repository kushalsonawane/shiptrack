"""Local SMTP catcher for development (no mail credentials needed).

The ShipTrack backend sends email over real SMTP. Until SMIPL provides mail
credentials, point the backend at this catcher: it accepts the exact same SMTP
conversation and saves every message to backend/data/maildrop/ as an .eml file
(open it with any mail client to see the email and its PDF attachments).

Run:
    .venv\\Scripts\\python.exe tools\\smtp_catcher.py [port]      (default 2525)

Then in backend/.env:
    SMTP_HOST=127.0.0.1
    SMTP_PORT=2525
    SMTP_STARTTLS=false
"""

import email
import re
import socketserver
import sys
from datetime import datetime
from email import policy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DROP_DIR = BASE_DIR / "data" / "maildrop"
DROP_DIR.mkdir(parents=True, exist_ok=True)


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or ""))[:60] or "message"


class CatcherHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 shiptrack-smtp-catcher ready\r\n")
        data_mode = False
        buffer = b""
        while True:
            line = self.rfile.readline()
            if not line:
                break
            if data_mode:
                if line in (b".\r\n", b".\n"):
                    data_mode = False
                    self._store(buffer)
                    self.wfile.write(b"250 OK queued\r\n")
                else:
                    buffer += line
                continue

            command = line.decode("utf-8", "ignore").strip()
            upper = command.upper()
            if upper.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-shiptrack-smtp-catcher\r\n250 SIZE 26214400\r\n")
            elif upper.startswith(("MAIL FROM", "RCPT TO")):
                self.wfile.write(b"250 OK\r\n")
            elif upper.startswith("DATA"):
                buffer = b""
                data_mode = True
                self.wfile.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
            elif upper.startswith("RSET"):
                buffer = b""
                self.wfile.write(b"250 OK\r\n")
            elif upper.startswith("QUIT"):
                self.wfile.write(b"221 Bye\r\n")
                break
            else:
                self.wfile.write(b"250 OK\r\n")

    def _store(self, raw: bytes):
        message = email.message_from_bytes(raw, policy=policy.default)
        to = message.get("To", "unknown")
        subject = message.get("Subject", "(no subject)")
        attachments = [part.get_filename() for part in message.walk() if part.get_filename()]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        filename = f"{stamp}-{_safe(to)}.eml"
        (DROP_DIR / filename).write_bytes(raw)
        names = ", ".join(name for name in attachments if name) or "-"
        print(
            f"[{stamp}] To: {to} | Subject: {subject} | {len(attachments)} attachment(s): {names} -> {filename}",
            flush=True,
        )

class Catcher(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2525
    server = Catcher(("127.0.0.1", port), CatcherHandler)
    print(f"SMTP catcher listening on 127.0.0.1:{port}", flush=True)
    print(f"Saving messages to {DROP_DIR}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
