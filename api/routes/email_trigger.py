from flask import Blueprint, jsonify, request
from email_service.email_sender import fetch_personalized_suggestions, send_personalized_email

email_trigger = Blueprint('email_trigger', __name__)

@email_trigger.route('/send_daily_email', methods=['GET'])
def send_daily_email():
    """
    Trigger the sending of a daily personalized email.

    Example:
        curl "https://.../send_daily_email?user_id=asako&email=asako.nishibe@gmail.com"
    """
    user_id = request.args.get("user_id")
    email = request.args.get("email")

    if not user_id or not email:
        return jsonify({"error": "Missing required query parameters 'user_id' and/or 'email'"}), 400

    suggestions = fetch_personalized_suggestions(user_id)
    if not suggestions:
        return jsonify({"error": f"No suggestions found for user_id: {user_id}"}), 404

    send_personalized_email(email, suggestions)
    return jsonify({"message": f"✅ Email sent to {email} for user {user_id}"}), 200
