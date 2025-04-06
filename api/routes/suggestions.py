import os
from google.cloud import firestore
import requests
from flask import Blueprint, jsonify
from urllib.parse import quote_plus

suggestions = Blueprint('suggestions', __name__)

@suggestions.route('/suggestions', methods=['GET'])
def get_suggestions():
    # Generic default values for non-personalized search
    cuisine = "Italian restaurant"
    city = "Tokyo"
    
    # Use Tokyo coordinates as a global default
    location = "35.6895,139.6917"
    radius = 1500  # in meters
    encoded_keyword = quote_plus(cuisine)
    api_key = os.environ.get("MAPS_API_KEY", "MISSING_KEY")
    
    google_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={location}&radius={radius}&keyword={encoded_keyword}&key={api_key}"
    )
    
    response = requests.get(google_url)
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        suggestions_list = []
        for place in results:
            name = place.get("name")
            address = place.get("vicinity")
            rating = place.get("rating", "N/A")
            total_reviews = place.get("user_ratings_total", "N/A")
            
            # Get main photo URL if available
            photo_url = None
            if "photos" in place and place["photos"]:
                photo_ref = place["photos"][0].get("photo_reference")
                if photo_ref:
                    photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_ref}&key={api_key}"
            
            # Fetch latest review snippet using Place Details API
            latest_review = "No reviews available"
            place_id = place.get("place_id")
            if place_id:
                details_url = (
                    f"https://maps.googleapis.com/maps/api/place/details/json?"
                    f"place_id={place_id}&fields=reviews&key={api_key}"
                )
                details_response = requests.get(details_url)
                if details_response.status_code == 200:
                    details_data = details_response.json()
                    reviews = details_data.get("result", {}).get("reviews", [])
                    if reviews:
                        latest_review = reviews[0].get("text", "No review text")
            
            suggestions_list.append({
                "name": name,
                "address": address,
                "rating": rating,
                "total_reviews": total_reviews,
                "photo_url": photo_url,
                "latest_review": latest_review
            })
        return jsonify({"suggestions": suggestions_list})
    else:
        return jsonify({"suggestions": []}), response.status_code

@suggestions.route('/suggestions/<user_id>', methods=['GET'])
def get_suggestions_for_user(user_id):
    db = firestore.Client()

    # Retrieve user preferences from Firestore
    doc_ref = db.collection('preferences').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        prefs = doc.to_dict()
        # Use Firestore values (if not provided, they may be empty)
        cuisine = prefs.get("cuisine", "").strip()
        city = prefs.get("city", "").strip()
    else:
        # Fall back to defaults if no preferences are found
        cuisine = "Italian restaurant"
        city = "Tokyo"
    
    # Mapping cities to coordinates.
    city_coords = {
        "Tokyo": "35.6895,139.6917",
        "New York": "40.7128,-74.0060",
        "London": "51.5074,-0.1278"
    }
    # If the user's city isn't defined or recognized, fallback to Tokyo's coordinates.
    location = city_coords.get(city, "35.6895,139.6917")
    radius = 1500  # in meters
    encoded_keyword = quote_plus(cuisine if cuisine else "Italian restaurant")
    api_key = os.environ.get("MAPS_API_KEY", "MISSING_KEY")
    
    google_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
        f"location={location}&radius={radius}&keyword={encoded_keyword}&key={api_key}"
    )
    
    response = requests.get(google_url)
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        suggestions_list = []
        for place in results:
            name = place.get("name")
            address = place.get("vicinity")
            rating = place.get("rating", "N/A")
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
                details_response = requests.get(details_url)
                if details_response.status_code == 200:
                    details_data = details_response.json()
                    reviews = details_data.get("result", {}).get("reviews", [])
                    if reviews:
                        latest_review = reviews[0].get("text", "No review text")
            
            suggestions_list.append({
                "name": name,
                "address": address,
                "rating": rating,
                "total_reviews": total_reviews,
                "photo_url": photo_url,
                "latest_review": latest_review
            })
        return jsonify({"suggestions": suggestions_list}), 200
    else:
        return jsonify({"suggestions": []}), response.status_code
