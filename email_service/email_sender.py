import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader

def send_suggestion_email(recipient_email, suggestions):
    # Load email template
    env = Environment(loader=FileSystemLoader('email_service/templates'))
    template = env.get_template('suggestion_email.html')
    html_content = template.render(suggestions=suggestions)

    # Configure email details (adjust SMTP settings as needed)
    msg = MIMEText(html_content, 'html')
    msg['Subject'] = "Daily Italian Restaurant Suggestions"
    msg['From'] = "noreply@example.com"
    msg['To'] = recipient_email

    # Example: Using SMTP server; replace with your SMTP configuration.
    with smtplib.SMTP('smtp.example.com', 587) as server:
        server.starttls()
        server.login("your_username", "your_password")
        server.send_message(msg)

if __name__ == '__main__':
    # Example usage:
    suggestions = [
        {"name": "Luigi's Italian Restaurant", "address": "123 Pasta Lane", "rating": 4.5},
        {"name": "Mario's Trattoria", "address": "456 Pizza Street", "rating": 4.3},
        {"name": "Bella Cucina", "address": "789 Risotto Rd", "rating": 4.7}
    ]
    send_suggestion_email("user@example.com", suggestions)
