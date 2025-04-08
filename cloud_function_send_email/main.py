import os
import requests
import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader

def send_email(request):
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")

    user_id = "user123"
    suggestions_url = f"{CLOUD_RUN_URL}/suggestions/{user_id}"

    try:
        response = requests.get(suggestions_url)
        suggestions = response.json().get("suggestions", []) if response.status_code == 200 else []
    except:
        suggestions = []

    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('suggestion_email.html')
    html_content = template.render(suggestions=suggestions)

    msg = MIMEText(html_content, 'html')
    msg['Subject'] = "Your Daily Personalized Restaurant Suggestions"
    msg['From'] = SENDER_EMAIL
    msg['To'] = SENDER_EMAIL

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return "Email sent successfully", 200
    except Exception as e:
        return f"Email failed: {e}", 500
