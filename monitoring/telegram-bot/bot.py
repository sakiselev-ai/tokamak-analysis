from __future__ import annotations
"""Telegram bot for Prometheus alerts.

Receives webhooks from Alertmanager and forwards to Telegram chat.
Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.

Usage:
    TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python bot.py
"""
import json
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
PORT = int(os.environ.get("PORT", "5000"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-alert")

SEVERITY_RU = {
    "critical": "критический",
    "warning": "предупреждение",
    "info": "информация",
}

STATUS_RU = {
    "firing": "СРАБОТАЛ",
    "resolved": "РЕШЕНО",
}


def send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set, skipping notification")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }).encode()

    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        logger.info("Telegram notification sent")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


def format_alert(alert: dict) -> str:
    status = alert.get("status", "unknown")
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})

    is_firing = status.lower() == "firing"
    emoji = "\U0001f534" if is_firing else "\u2705"
    status_text = STATUS_RU.get(status.lower(), status.upper())
    severity = labels.get("severity", "unknown")
    severity_text = SEVERITY_RU.get(severity, severity)
    name = labels.get("alertname", "Unknown")
    summary = annotations.get("summary", "Нет описания")
    description = annotations.get("description", "")

    msg = f"{emoji} <b>{status_text}: {name}</b>\n"
    msg += f"Уровень: {severity_text}\n"
    msg += f"Описание: {summary}\n"
    if description:
        msg += f"Подробности: {description}\n"
    if is_firing:
        starts_at = alert.get("startsAt", "")
        if starts_at:
            msg += f"Начало: {starts_at[:19].replace('T', ' ')}\n"
    else:
        ends_at = alert.get("endsAt", "")
        if ends_at:
            msg += f"Завершено: {ends_at[:19].replace('T', ' ')}\n"
    msg += f"Источник: Tokamak Analysis Platform"

    return msg


class AlertHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)
            alerts = payload.get("alerts", [])

            for alert in alerts:
                message = format_alert(alert)
                send_telegram(message)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        logger.info(format % args)


if __name__ == "__main__":
    logger.info(f"Starting Telegram alert bot on port {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), AlertHandler)
    server.serve_forever()
