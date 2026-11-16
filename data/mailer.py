"""E-Mails verschicken (Bestaetigung, Passwort zuruecksetzen, Hinweise).

SMTP-Zugang aus config.yaml (mail.*); das Passwort als systemd-Credential
"pomodoro-smtp-password" oder Datei <accounts.key_dir>/smtp.password --
nie als Umgebungsvariable (KONZEPT-ACCOUNTS.md, 8).

Ohne mail.host (Entwicklung, Tests) landet die Mail in OUTBOX und auf der
Konsole. Verschickt wird asynchron, damit die Antwortzeit nicht verraet,
ob es ein Konto gibt.

Keine Flask-Importe.
"""

import smtplib
import threading
from email.message import EmailMessage

from data.appconfig import CONFIG

MAIL = CONFIG["mail"]

#: Zuletzt "verschickte" Mails ohne SMTP -- fuer Tests und Entwicklung.
OUTBOX = []
_outbox_lock = threading.Lock()


def _smtp_password():
    from data import crypto
    raw = crypto._read_secret("pomodoro-smtp-password", "smtp.password", required=False)
    return raw.decode("utf-8").strip() if raw else None


def send(to, subject, body):
    if not MAIL.get("host"):
        with _outbox_lock:
            OUTBOX.append({"to": to, "subject": subject, "body": body})
            del OUTBOX[:-100]
        print("[Mail, kein SMTP konfiguriert] an %s: %s\n%s" % (to, subject, body))
        return True
    message = EmailMessage()
    message["From"] = MAIL.get("sender")
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(MAIL["host"], int(MAIL.get("port") or 587), timeout=20) as smtp:
            if MAIL.get("starttls", True):
                smtp.starttls()
            if MAIL.get("user"):
                smtp.login(MAIL["user"], _smtp_password() or "")
            smtp.send_message(message)
        return True
    except Exception as exc:  # Mail darf nie eine Anfrage abbrechen
        print("Mail an %s fehlgeschlagen: %s" % (to, exc))
        return False


def send_async(to, subject, body):
    threading.Thread(target=send, args=(to, subject, body), daemon=True).start()
