from google.cloud import firestore
import requests
from flask import Blueprint, jsonify
from urllib.parse import quote_plus

suggestions = Blueprint('suggestions', __name__)

# Default endpoint (no user preferences)
@suggestions.route('/suggestions', methods=['GET'])
def get_suggestions():
    # Use fixed default parameters: Tokyo, Italian restaurant
    api_key = "AIzaSyCvXUPVqtLK-sME0d10Z9m3oyye1wZQFu4"
    location = "35.6895,139.6917"  # Tokyo coordinates
    radius = 1500  # in meters
    keyword = "Italian restaurant"
    encoded_keyword = quote_plus(keyword)

    google_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={location}&radius={radius}&keyword={encoded_keyword}&key={api_key}"
    )

    print("DEBUG default URL:", google_url)
    response = requests.get(google_url)
    print("DEBUG default response status:", response.status_code)
    print("DEBUG default response text:", response.text)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        suggestions_list = [
            {
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "rating": place.get("rating", "N/A")
            }
            for place in results
        ]
        return jsonify({"suggestions": suggestions_list})
    else:
        return jsonify({"suggestions": []}), response.status_code


# Personalized endpoint: uses user preferences from Firestore
@suggestions.route('/suggestions/<user_id>', methods=['GET'])
def get_suggestions_for_user(user_id):
    # Initialize Firestore client
    db = firestore.Client()

    # Retrieve user preferences from Firestore
    doc_ref = db.collection('preferences').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        prefs = doc.to_dict()
        # Strip extra spaces if any
        cuisine = prefs.get("cuisine", "Italian restaurant").strip()
        city = prefs.get("city", "Tokyo").strip()
        print("DEBUG preferences from Firestore:", cuisine, city)
    else:
        cuisine = "Italian restaurant"
        city = "Tokyo"
        print("DEBUG no preferences found for user", user_id, "using defaults:", cuisine, city)

    # Map city to lat,lng coordinates
    city_coords = {
        "Tokyo": "35.6895,139.6917",
        "New York": "40.7128,-74.0060",
        "London": "51.5074,-0.1278"
    }
    location = city_coords.get(city, "35.6895,139.6917")
    radius = 1500
    keyword = cuisine
    encoded_keyword = quote_plus(keyword)
    api_key = "AIzaSyCvXUPVqtLK-sME0d10Z9m3oyye1wZQFu4"

    google_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={location}&radius={radius}&keyword={encoded_keyword}&key={api_key}"
    )

    print("DEBUG (user-specific) URL:", google_url)
    response = requests.get(google_url)
    print("DEBUG (user-specific) response status:", response.status_code)
    print("DEBUG (user-specific) response text:", response.text)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        suggestions_list = [
            {
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "rating": place.get("rating", "N/A")
            }
            for place in results
        ]
        return jsonify({"suggestions": suggestions_list}), 200
    else:
        return jsonify({"suggestions": []}), response.status_code
