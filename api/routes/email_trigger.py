from flask import Blueprint, jsonify
# Import the email sender functions from your email_sender module
from email_service.email_sender import fetch_personalized_suggestions, send_personalized_email

email_trigger = Blueprint('email_trigger', __name__)

@email_trigger.route('/send_daily_email', methods=['GET'])
def send_daily_email():
    """
    Trigger the sending of a daily personalized email.
    This endpoint can be called by Cloud Scheduler.
    """
    user_id = "user123"  # For testing, use a fixed user ID (you can extend this later)
    # Fetch suggestions using the personalized endpoint logic
    suggestions = fetch_personalized_suggestions(user_id)
    # Send the email (change the recipient as needed)
    send_personalized_email("kopser@gmail.com", suggestions)
    return jsonify({"message": "Daily email triggered and sent"}), 200
