import os
import requests
import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Email sender is running.", 200

@app.route('/send_email', methods=['POST'])
def send_email():
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")

    user_id = "user123"
    suggestions_url = f"{CLOUD_RUN_URL}/suggestions/{user_id}"

    print(f"📡 Fetching suggestions from: {suggestions_url}", flush=True)

    try:
        response = requests.get(suggestions_url)
        if response.status_code != 200:
            print(f"❌ Failed to fetch suggestions. Status: {response.status_code}", flush=True)
            return "Failed to fetch suggestions", 500

        suggestions = response.json().get("suggestions", [])
        print(f"✅ Received {len(suggestions)} suggestions", flush=True)

    except Exception as e:
        print(f"🔥 Exception during suggestion fetch: {e}", flush=True)
        return f"Exception during fetch: {e}", 500

    try:
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('suggestion_email.html')
        html_content = template.render(suggestions=suggestions)

        msg = MIMEText(html_content, 'html')
        msg['Subject'] = "Your Daily Personalized Restaurant Suggestions"
        msg['From'] = SENDER_EMAIL
        msg['To'] = SENDER_EMAIL

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully", flush=True)
        return "Email sent successfully", 200

    except Exception as e:
        print(f"❌ Email send failed: {e}", flush=True)
        return f"Email failed: {e}", 500
