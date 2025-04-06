import os
import requests
import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

# Load environment variables (if needed for local testing)
load_dotenv()

# Environment variables will be provided during deployment.
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")  # URL of your deployed Cloud Run service

def send_email(request):
    """
    Cloud Function entry point.
    This function is triggered by an HTTP request.
    It fetches suggestions from your Cloud Run service and sends an email.
    """
    # Set a test user_id (you can modify this if needed)
    user_id = "user123"
    suggestions_url = f"{CLOUD_RUN_URL}/suggestions/{user_id}"
    
    try:
        response = requests.get(suggestions_url)
        if response.status_code == 200:
            data = response.json()
            suggestions = data.get("suggestions", [])
        else:
            suggestions = []
    except Exception as e:
        suggestions = []
    
    # Load the email template from the templates folder
    env = Environment(loader=FileSystemLoader('templates'))
    try:
        template = env.get_template('suggestion_email.html')
    except Exception as e:
        return f"Template error: {e}", 500
    
    html_content = template.render(suggestions=suggestions)

    # Configure the email message
    msg = MIMEText(html_content, 'html')
    msg['Subject'] = "Your Daily Personalized Restaurant Suggestions"
    msg['From'] = SENDER_EMAIL
    msg['To'] = SENDER_EMAIL  # For testing, sending to yourself

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return "Email sent successfully", 200
    except Exception as e:
        return f"Error sending email: {e}", 500
