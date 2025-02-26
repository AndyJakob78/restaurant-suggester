from flask import Blueprint, jsonify

suggestions = Blueprint('suggestions', __name__)

@suggestions.route('/suggestions', methods=['GET'])
def get_suggestions():
    # Placeholder: Replace with AI model inference later.
    dummy_response = {
        "suggestions": [
            {"name": "Luigi's Italian Restaurant", "address": "123 Pasta Lane", "rating": 4.5},
            {"name": "Mario's Trattoria", "address": "456 Pizza Street", "rating": 4.3},
            {"name": "Bella Cucina", "address": "789 Risotto Rd", "rating": 4.7}
        ]
    }
    return jsonify(dummy_response), 200
