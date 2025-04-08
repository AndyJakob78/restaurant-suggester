import os
import random
from google.cloud import firestore
import requests
from flask import Blueprint, jsonify
from urllib.parse import quote_plus
from inference import load_model, get_prediction

suggestions = Blueprint('suggestions', __name__)
model = load_model()

# 🔁 Shared logic for both endpoints
def filter_and_format_results(results, api_key, prefix="default", user_id=None):
    suggestions_list = []
    for place in results:
        name = place.get("name")
        address = place.get("vicinity")
        rating = place.get("rating", "0")
        total_reviews = place.get("user_ratings_total", "N/A")
        photo_url = None
        if "photos" in place and place["photos"]:
            photo_ref = place["photos"][0].get("photo_reference")
            if photo_ref:
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_ref}&key={api_key}"

        latest_review = "No reviews available"
        place_id = place.get("place_id")
        if place_id:
            details_url = (
                f"https://maps.googleapis.com/maps/api/place/details/json?"
                f"place_id={place_id}&fields=reviews&key={api_key}"
            )
            print(f"DEBUG [{prefix}] details_url:", details_url, flush=True)
            details_response = requests.get(details_url)
            if details_response.status_code == 200:
                details_data = details_response.json()
                reviews = details_data.get("result", {}).get("reviews", [])
                if reviews:
                    latest_review = reviews[0].get("text", "No review text")

        # Run ML inference
        try:
            score = get_prediction([float(rating), 1.0], model)
        except Exception as e:
            print("Prediction failed:", e)
            score = 0

        if score == 1:
            suggestions_list.append({
                "name": name,
                "address": address,
                "rating": rating,
                "total_reviews": total_reviews,
                "photo_url": photo_url,
                "latest_review": latest_review
            })

    # Shuffle suggestions to provide variety
    random.shuffle(suggestions_list)
    return suggestions_list

@suggestions.route('/suggestions', methods=['GET'])
def get_suggestions():
    return jsonify({"error": "Please use the /suggestions/<user_id> endpoint."}), 400

@suggestions.route('/suggestions/<user_id>', methods=['GET'])
def get_suggestions_for_user(user_id):
    db = firestore.Client()
    doc_ref = db.collection('preferences').document(user_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"error": "No preferences found for user."}), 404

    prefs = doc.to_dict()
    cuisine = prefs.get("cuisine")
    location = prefs.get("location")

    if not cuisine or not location:
        return jsonify({"error": "User preferences must include both 'cuisine' and 'location'."}), 400

    cuisine = cuisine.strip()
    location = location.strip()
    radius = 1500
    encoded_keyword = quote_plus(cuisine)
    api_key = os.environ.get("MAPS_API_KEY", "MISSING_KEY")

    google_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={location}&radius={radius}&keyword={encoded_keyword}&key={api_key}"
    )

    print("DEBUG [personalized] google_url:", google_url, flush=True)
    response = requests.get(google_url)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        suggestions_list = filter_and_format_results(results, api_key, prefix="personalized", user_id=user_id)
        return jsonify({"suggestions": suggestions_list})
    else:
        return jsonify({"suggestions": []}), response.status_code
