from flask import Blueprint, request, jsonify
from google.cloud import firestore

# Create a blueprint for user preferences
preferences_bp = Blueprint('preferences_bp', __name__)

# Initialize Firestore client
db = firestore.Client()

@preferences_bp.route('/preferences', methods=['POST'])
def set_preferences():
    """
    Store or update user preferences.

    Expected JSON body:
    {
        "user_id": "user123",
        "preferences": {
            "cuisine": "Italian",
            "location": "35.6895,139.6917",
            "query_variants": ["trattoria", "italian", "osteria"]
        }
    }
    """
    data = request.get_json()
    user_id = data.get("user_id")
    prefs = data.get("preferences")

    if not user_id or not prefs:
        return jsonify({"error": "Missing user_id or preferences"}), 400

    if not prefs.get("cuisine") or not prefs.get("location"):
        return jsonify({"error": "Preferences must include 'cuisine' and 'location'"}), 400

    db.collection("preferences").document(user_id).set(prefs)
    return jsonify({"message": f"Preferences for user '{user_id}' updated successfully."}), 200

@preferences_bp.route('/preferences/<user_id>', methods=['GET'])
def get_preferences(user_id):
    """
    Retrieve stored preferences for a specific user.
    """
    doc_ref = db.collection("preferences").document(user_id)
    doc = doc_ref.get()

    if doc.exists:
        return jsonify(doc.to_dict()), 200
    else:
        return jsonify({"error": f"No preferences found for user '{user_id}'."}), 404
