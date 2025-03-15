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
          "city": "Tokyo"
        }
      }
    """
    data = request.get_json()
    user_id = data.get('user_id')
    user_preferences = data.get('preferences')

    if not user_id or not user_preferences:
        return jsonify({"error": "Missing user_id or preferences"}), 400

    # Save preferences in a Firestore collection named "preferences"
    doc_ref = db.collection('preferences').document(user_id)
    doc_ref.set(user_preferences)
    return jsonify({"message": "Preferences updated successfully"}), 200

@preferences_bp.route('/preferences/<user_id>', methods=['GET'])
def get_preferences(user_id):
    """
    Retrieve user preferences by user_id.
    """
    doc_ref = db.collection('preferences').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        return jsonify(doc.to_dict()), 200
    else:
        return jsonify({"error": "No preferences found for this user"}), 404
