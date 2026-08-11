"""
Powiadomienia o nowych wejściach do TOP 10 wybranej strategii — wysyłane po
codziennym skanie (patrz scripts/run_daily_scan.py, uruchamiane przez GitHub
Actions). To jedyne miejsce, które działa bez Twojego udziału — appka
Streamlit sama z siebie nie "pilnuje" niczego w tle.

Wszystkie kanały są OPCJONALNE i włączają się same, gdy odpowiednie sekrety
GitHub Actions są ustawione (Settings → Secrets and variables → Actions):
  - Discord:  DISCORD_WEBHOOK_URL
  - Telegram: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  - E-mail:   EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO

Bez ustawionych sekretów cały moduł cicho nic nie robi — nie trzeba zmieniać
kodu, żeby włączyć/wyłączyć dowolny kanał, wystarczy dodać/usunąć sekret.
NIGDY nie wpisuj tych wartości bezpośrednio w kodzie źródłowym.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

import pandas as pd
import requests


def _discord_configured() -> bool:
    return bool(os.environ.get("DISCORD_WEBHOOK_URL"))


def _telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def _email_configured() -> bool:
    return bool(
        os.environ.get("EMAIL_SMTP_HOST") and os.environ.get("EMAIL_FROM")
        and os.environ.get("EMAIL_PASSWORD") and os.environ.get("EMAIL_TO")
    )


def any_channel_configured() -> bool:
    return _discord_configured() or _telegram_configured() or _email_configured()


def send_discord(message: str) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return
    try:
        requests.post(url, json={"content": message[:1900]}, timeout=15)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Nie udało się wysłać powiadomienia Discord: {e}")


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": message[:4000]}, timeout=15)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Nie udało się wysłać powiadomienia Telegram: {e}")


def send_email(subject: str, message: str) -> None:
    host = os.environ.get("EMAIL_SMTP_HOST")
    port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    sender = os.environ.get("EMAIL_FROM")
    password = os.environ.get("EMAIL_PASSWORD")
    to = os.environ.get("EMAIL_TO")
    if not (host and sender and password and to):
        return
    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [to], msg.as_string())
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Nie udało się wysłać e-maila: {e}")


def broadcast(subject: str, message: str) -> None:
    """Wysyła wiadomość na wszystkie skonfigurowane kanały naraz."""
    if not any_channel_configured():
        return
    send_discord(message)
    send_telegram(message)
    send_email(subject, message)


def check_top10_newcomers(strategies: dict, today_df: pd.DataFrame, prev_df: pd.DataFrame | None) -> None:
    """
    Dla każdej strategii porównuje dzisiejszy TOP 10 z wczorajszym i wysyła
    JEDNO zbiorcze powiadomienie o nowych wejściach (spółkach, które dziś
    wskoczyły do TOP 10, a wczoraj ich tam nie było) — żeby nie spamować
    powiadomieniem o tych samych spółkach co dzień.
    """
    if not any_channel_configured():
        print("ℹ️ Brak skonfigurowanych kanałów powiadomień — pomijam sprawdzanie TOP 10.")
        return

    stocks_today = today_df[today_df["Typ"] == "stock"]
    lines: list[str] = []

    for name, (score_col, _) in strategies.items():
        if score_col not in stocks_today.columns:
            continue
        top_today = set(stocks_today.sort_values(score_col, ascending=False).head(10)["Ticker"])

        top_prev: set[str] = set()
        if prev_df is not None and not prev_df.empty:
            stocks_prev = prev_df[prev_df["Typ"] == "stock"]
            if score_col in stocks_prev.columns:
                top_prev = set(stocks_prev.sort_values(score_col, ascending=False).head(10)["Ticker"])

        newcomers = top_today - top_prev
        if newcomers:
            names = stocks_today.set_index("Ticker")["Nazwa"]
            entries = ", ".join(f"{t} ({names.get(t, t)})" for t in sorted(newcomers))
            lines.append(f"📈 {name}: nowe wejścia do TOP 10 — {entries}")

    if lines:
        message = "🔔 XTB Screener — nowe wejścia do TOP 10\n\n" + "\n".join(lines)
        broadcast("XTB Screener — nowe wejścia do TOP 10", message)
        print("✅ Wysłano powiadomienia o nowych wejściach do TOP 10.")
    else:
        print("ℹ️ Brak nowych wejść do TOP 10 żadnej strategii — bez powiadomień.")
