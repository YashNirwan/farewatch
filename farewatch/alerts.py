"""Send alerts via Telegram if configured, otherwise macOS notification + stdout."""

import os
import re
import shutil
import subprocess

import requests


def _first_url(text):
    m = re.search(r"https?://\S+", text or "")
    return m.group() if m else None


def send(title, body):
    print(f"\n🚨 {title}\n{body}\n")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"{title}\n\n{body}"},
                timeout=30,
            ).raise_for_status()
            return
        except requests.RequestException as e:
            print(f"Telegram send failed ({e}); falling back to local notification.")
    notifier = shutil.which("terminal-notifier") or next(
        (p for p in ("/opt/homebrew/bin/terminal-notifier", "/usr/local/bin/terminal-notifier")
         if os.path.exists(p)), None)
    if notifier:
        cmd = [notifier, "-title", title, "-message", body, "-sound", "Glass"]
        url = _first_url(body)
        if url:
            cmd += ["-open", url]
        subprocess.run(cmd, check=False, capture_output=True)
        return
    try:
        subprocess.run(
            [
                "osascript", "-e",
                f'display notification {_osa_quote(body)} with title {_osa_quote(title)} sound name "Glass"',
            ],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


def _osa_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
