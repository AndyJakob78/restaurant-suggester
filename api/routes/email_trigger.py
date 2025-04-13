from flask import Blueprint, jsonify, request
from email_service.email_sender import fetch_personalized_suggestions, send_personalized_email

email_trigger = Blueprint('email_trigger', __name__)

@email_trigger.route('/send_daily_email', methods=['GET'])
def send_daily_email():
    """
    Trigger the sending of a daily personalized email.
    You can call this via a browser, curl, or Cloud Scheduler.

    Example:
        curl "https://.../send_daily_email?user_id=alice123"
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing required query parameter 'user_id'"}), 400

    suggestions = fetch_personalized_suggestions(user_id)
    send_personalized_email("kopser@gmail.com", suggestions)  # Change recipient if needed
    return jsonify({"message": f"Daily email triggered and sent for user {user_id}"}), 200
