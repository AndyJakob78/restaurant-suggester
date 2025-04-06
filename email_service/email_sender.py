import os
import requests
import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set your live Cloud Run service URL
CLOUD_RUN_URL = "https://restaurant-suggester-726264366097.asia-northeast1.run.app"

# Retrieve your sender email and app password from environment variables
SENDER_EMAIL = os.getenv("SENDER_EMAIL")  # e.g., "kopser@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # e.g., "your_app_password"

def fetch_personalized_suggestions(user_id):
    """
    Fetch personalized suggestions from your live Cloud Run service for a given user_id.
    """
    url = f"{CLOUD_RUN_URL}/suggestions/{user_id}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("suggestions", [])
        else:
            print("Error fetching suggestions. Status code:", response.status_code)
            return []
    except Exception as e:
        print("Exception fetching suggestions:", e)
        return []

def send_personalized_email(recipient_email, suggestions):
    """
    Render an email template with personalized suggestions and send the email.
    """
    # Load the email template (ensure this file exists in email_service/templates)
    env = Environment(loader=FileSystemLoader('email_service/templates'))
    template = env.get_template('suggestion_email.html')
    html_content = template.render(suggestions=suggestions)

    # Configure the email message
    msg = MIMEText(html_content, 'html')
    msg['Subject'] = "Your Daily Personalized Restaurant Suggestions"
    msg['From'] = SENDER_EMAIL  # Using sender email from environment
    msg['To'] = recipient_email

    # Send the email using Gmail's SMTP server
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully!")
    except Exception as e:
        print("Error sending email:", e)

if __name__ == '__main__':
    # Use a test user_id, for example "user123"
    user_id = "user123"
    suggestions = fetch_personalized_suggestions(user_id)
    print("Fetched personalized suggestions:", suggestions)
    # Replace the recipient email with your actual email address for testing
    send_personalized_email(SENDER_EMAIL, suggestions)
