import os
import random
import time
from google.cloud import firestore
import requests
from flask import Blueprint, jsonify
from ml.inference import load_model, get_prediction

suggestions = Blueprint('suggestions', __name__)
model = load_model()

# 🔁 Shared logic for both endpoints
def filter_and_format_results(places, user_id=None):
    db = firestore.Client()
    sent_place_ids = set()
    if user_id:
        history_ref = db.collection("history").document(user_id)
        history_doc = history_ref.get()
        if history_doc.exists:
            sent_place_ids = set(history_doc.to_dict().get("place_ids", []))

    def process_places(skip_history):
        result_list = []
        for place in places:
            place_id = place.get("id")
            if not place_id:
                continue
            if skip_history is False and place_id in sent_place_ids:
                continue

            name = place.get("displayName", {}).get("text")
            address = place.get("formattedAddress")
            rating = place.get("rating", 0.0)
            total_reviews = place.get("userRatingCount", "N/A")

            photo_url = None
            if "photos" in place and place["photos"]:
                photo_ref = place["photos"][0].get("name")
                if photo_ref:
                    photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=400&key={os.environ.get('MAPS_API_KEY')}"

            # Run ML inference
            try:
                score = get_prediction([float(rating), 1.0], model)
            except Exception as e:
                print("Prediction failed:", e)
                score = 0

            if score == 1:
                result_list.append({
                    "name": name,
                    "address": address,
                    "rating": rating,
                    "total_reviews": total_reviews,
                    "photo_url": photo_url,
                    "place_id": place_id,
                    "latest_review": "Reviews not available with new API"
                })
        return result_list

    # First attempt: with deduplication
    suggestions_list = process_places(skip_history=False)

    # Fallback: no deduplication if nothing found
    if not suggestions_list and user_id:
        print("⚠️ No new suggestions after filtering. Retrying without history filter...", flush=True)
        suggestions_list = process_places(skip_history=True)

    # Shuffle suggestions
    random.seed(time.time())
    random.shuffle(suggestions_list)
    print("Final shuffled suggestions:", [repr(s["name"]) for s in suggestions_list], flush=True)

    # Save top 3
    if user_id and suggestions_list:
        try:
            history_ref = db.collection("history").document(user_id)
            history_doc = history_ref.get()
            previous_ids = history_doc.to_dict().get("place_ids", []) if history_doc.exists else []
            returned_place_ids = [s["place_id"] for s in suggestions_list[:3]]
            updated_ids = list(set(previous_ids + returned_place_ids))[:50]

            db.collection("history").document(user_id).set({
                "place_ids": updated_ids,
                "last_sent": firestore.SERVER_TIMESTAMP
            })
            print("📄 Stored top 3 sent suggestions in Firestore.", flush=True)
        except Exception as e:
            print("🚨 Failed to save suggestion history:", e, flush=True)

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

    cuisine = cuisine.strip().lower().replace(" ", "_") + "_restaurant"
    lat, lng = map(float, location.split(","))

    api_key = os.environ.get("MAPS_API_KEY", "MISSING_KEY")

    query_payload = {
        "textQuery": cuisine.replace("_", " "),
        "includedType": cuisine,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 2500.0
            }
        },
        "pageSize": 20
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.photos"
    }

    print("DEBUG [Text Search] payload:", query_payload, flush=True)
    response = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers=headers,
        json=query_payload
    )

    if response.status_code == 200:
        places = response.json().get("places", [])
        suggestions_list = filter_and_format_results(places, user_id=user_id)
        return jsonify({"suggestions": suggestions_list})
    else:
        print("❌ Google Places Text Search API failed:", response.text, flush=True)
        return jsonify({"suggestions": []}), response.status_code