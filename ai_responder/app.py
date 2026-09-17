import os
import requests
import json
import html
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def ask_ai_triage(alert_name, description, severity):
    if not GEMINI_API_KEY:
        return "AI triage: API key not set.", "systemctl status node_exporter"

    prompt = (
        f"You are a Senior Linux NOC Engineer.\n"
        f"Alert: {alert_name} (Severity: {severity})\n"
        f"Description: {description}\n\n"
        f"Task:\n"
        f"1. Explain the incident in 2 short sentences.\n"
        f"2. Provide 3 exact bash commands to diagnose and fix it.\n\n"
        f"Return ONLY valid JSON matching this schema:\n"
        f"{{\n"
        f'  "analysis": "Short 2-sentence explanation",\n'
        f'  "commands": "command 1\\ncommand 2\\ncommand 3"\n'
        f"}}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    # Retry up to 3 times with exponential backoff on transient errors (429, 500, 503)
    for attempt in range(1, 4):
        try:
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=12)
            if res.status_code == 200:
                content = res.json()['candidates'][0]['content']['parts'][0]['text']
                parsed = json.loads(content)
                return parsed.get("analysis", ""), parsed.get("commands", "")
            
            print(f"[WARN] Gemini attempt {attempt} failed ({res.status_code}): {res.text}", flush=True)
            if res.status_code in (429, 500, 503):
                time.sleep(2 * attempt)
                continue
            break
        except Exception as e:
            print(f"[WARN] Gemini attempt {attempt} exception: {e}", flush=True)
            time.sleep(2)

    # Deterministic fallback if API attempts fail completely
    return (
        "The target service is unreachable or stopped. Investigate host availability and daemon status.",
        "systemctl status node_exporter\nss -tulpn | grep 9100\njournalctl -u node_exporter -n 30 --no-pager"
    )

def send_telegram_alert(html_message, raw_text_fallback):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": html_message,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"[DEBUG] Telegram HTML status: {res.status_code}", flush=True)
        if res.status_code != 200:
            print(f"[ERROR] Telegram rejected HTML: {res.text}", flush=True)
            # Send guaranteed plain text fallback if Telegram parser fails
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": raw_text_fallback}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Telegram connection failed: {e}", flush=True)

@app.route('/webhook', methods=['POST'])
def receive_alert():
    data = request.get_json(silent=True)
    if not data or 'alerts' not in data:
        return jsonify({"status": "no alerts"}), 400

    for alert in data['alerts']:
        status = alert.get('status', 'firing').upper()
        labels = alert.get('labels', {})
        annotations = alert.get('annotations', {})

        alert_name = labels.get('alertname', 'Unknown')
        severity = labels.get('severity', 'INFO').upper()
        instance = labels.get('instance', 'N/A')
        description = annotations.get('description') or annotations.get('summary') or 'No description'

        safe_name = html.escape(alert_name)
        safe_instance = html.escape(instance)
        safe_desc = html.escape(description)

        # Scenario 1: Target recovered (RESOLVED)
        if status == "RESOLVED":
            msg_html = (
                f"✅ <b>[RESOLVED] {safe_name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Target:</b> <code>{safe_instance}</code>\n"
                f"• <b>Status:</b> Service recovered and responding normally.\n"
                f"• <b>Note:</b> {safe_desc}"
            )
            fallback_txt = f"[RESOLVED] {alert_name} on {instance} is back up."
            send_telegram_alert(msg_html, fallback_txt)
            continue

        # Scenario 2: Active incident (FIRING) -> Request AI triage
        analysis, commands = ask_ai_triage(alert_name, description, severity)

        safe_analysis = html.escape(analysis)
        safe_commands = html.escape(commands)

        msg_html = (
            f"🚨 <b>[{status}] {safe_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Severity:</b> {severity}\n"
            f"• <b>Target:</b> <code>{safe_instance}</code>\n"
            f"• <b>Description:</b> {safe_desc}\n\n"
            f"🛠 <b>AI NOC Diagnostic:</b>\n"
            f"{safe_analysis}\n\n"
            f"<b>Troubleshooting Commands:</b>\n"
            f'<pre><code class="language-bash">{safe_commands}</code></pre>'
        )

        fallback_txt = f"[{status}] {alert_name} on {instance}\n{description}\n\n{analysis}\n\nCommands:\n{commands}"
        send_telegram_alert(msg_html, fallback_txt)

    return jsonify({"status": "processed"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)