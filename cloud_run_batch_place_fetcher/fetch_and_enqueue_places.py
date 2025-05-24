import os
import time
import json
import logging
import requests
from google.cloud import firestore, pubsub_v1

# --- Config ---
MAPS_API_KEY = os.environ["MAPS_API_KEY"]
PROJECT_ID = os.environ.get("GCP_PROJECT", "restaurant-suggester-452114")
PUBSUB_TOPIC = "analyze-places-topic"

# --- Cuisine to Google Place Type Map (full, latest as of Nov 2024) ---
CUISINE_TYPE_MAP = {
    "acai": "acai_shop",
    "afghani": "afghani_restaurant",
    "african": "african_restaurant",
    "american": "american_restaurant",
    "asian": "asian_restaurant",
    "bagel": "bagel_shop",
    "bakery": "bakery",
    "bar": "bar",
    "bar and grill": "bar_and_grill",
    "barbecue": "barbecue_restaurant",
    "brazilian": "brazilian_restaurant",
    "breakfast": "breakfast_restaurant",
    "brunch": "brunch_restaurant",
    "buffet": "buffet_restaurant",
    "cafe": "cafe",
    "cafeteria": "cafeteria",
    "candy": "candy_store",
    "cat cafe": "cat_cafe",
    "chinese": "chinese_restaurant",
    "chocolate factory": "chocolate_factory",
    "chocolate shop": "chocolate_shop",
    "coffee": "coffee_shop",
    "confectionery": "confectionery",
    "deli": "deli",
    "dessert": "dessert_restaurant",
    "dessert shop": "dessert_shop",
    "diner": "diner",
    "dog cafe": "dog_cafe",
    "donut": "donut_shop",
    "fast food": "fast_food_restaurant",
    "fine dining": "fine_dining_restaurant",
    "food court": "food_court",
    "french": "french_restaurant",
    "greek": "greek_restaurant",
    "hamburger": "hamburger_restaurant",
    "ice cream": "ice_cream_shop",
    "indian": "indian_restaurant",
    "indonesian": "indonesian_restaurant",
    "italian": "italian_restaurant",
    "japanese": "japanese_restaurant",
    "juice": "juice_shop",
    "korean": "korean_restaurant",
    "lebanese": "lebanese_restaurant",
    "meal delivery": "meal_delivery",
    "meal takeaway": "meal_takeaway",
    "mediterranean": "mediterranean_restaurant",
    "mexican": "mexican_restaurant",
    "middle eastern": "middle_eastern_restaurant",
    "pizza": "pizza_restaurant",
    "pub": "pub",
    "ramen": "ramen_restaurant",
    "restaurant": "restaurant",
    "sandwich": "sandwich_shop",
    "seafood": "seafood_restaurant",
    "spanish": "spanish_restaurant",
    "steak": "steak_house",
    "sushi": "sushi_restaurant",
    "tea house": "tea_house",
    "thai": "thai_restaurant",
    "turkish": "turkish_restaurant",
    "vegan": "vegan_restaurant",
    "vegetarian": "vegetarian_restaurant",
    "vietnamese": "vietnamese_restaurant",
    "wine bar": "wine_bar",
}

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("place-fetcher")

# --- Clients ---
db = firestore.Client()
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)

def fetch_user_prefs():
    """Fetch all user preferences from Firestore."""
    users = db.collection("preferences").stream()
    prefs_list = []
    for doc in users:
        data = doc.to_dict()
        data["user_id"] = doc.id
        prefs_list.append(data)
    return prefs_list

def search_places_for_user(user):
    """Call Google Places API for this user's preferences."""
    cuisine = user.get("cuisine")
    location = user.get("location")
    variants = user.get("query_variants", []) or [cuisine]
    if not cuisine or not location:
        logger.warning(f"User {user['user_id']} missing cuisine or location. Skipping.")
        return []

    lat, lng = map(float, location.split(","))

    # Map cuisine to Google Place type, fallback to "restaurant"
    cuisine_type = CUISINE_TYPE_MAP.get(
        cuisine.strip().lower(), "restaurant"
    )
    if cuisine_type == "restaurant":
        logger.warning(f"Cuisine '{cuisine}' does not have a mapped place type. Using generic 'restaurant'.")

    all_places = []
    seen_ids = set()
    for variant in variants:
        payload = {
            "textQuery": variant,
            "includedType": cuisine_type,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 2500.0  # 2.5km
                }
            },
            "pageSize": 50
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": MAPS_API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,"
                                "places.rating,places.userRatingCount,places.photos,"
                                "places.generativeSummary"
        }

        next_token = None
        for _ in range(5):  # Up to 5 pages per variant (API max for Text Search is 5 pages)
            req_payload = payload.copy()
            if next_token:
                time.sleep(2)
                req_payload["pageToken"] = next_token

            resp = requests.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers=headers,
                json=req_payload,
                timeout=10
            )
            if resp.status_code != 200:
                logger.error(f"❌ Places API error: {resp.status_code} {resp.text}")
                break
            data = resp.json()
            for place in data.get("places", []):
                pid = place.get("id")
                if pid and pid not in seen_ids:
                    all_places.append(place)
                    seen_ids.add(pid)
            next_token = data.get("nextPageToken")
            if not next_token:
                break
    return all_places

def already_analyzed(place_id):
    """Check if place is already in place_analysis."""
    doc = db.collection("place_analysis").document(place_id).get()
    return doc.exists

def publish_for_analysis(place_id):
    """Publish place_id to Pub/Sub for analysis."""
    payload = {"place_id": place_id}
    publisher.publish(topic_path, json.dumps(payload).encode())
    logger.info(f"📬 Published place {place_id} to {PUBSUB_TOPIC}")

def main():
    users = fetch_user_prefs()
    logger.info(f"Fetched {len(users)} users from preferences")
    n_new = 0
    for user in users:
        logger.info(f"Fetching places for user: {user['user_id']} ({user.get('cuisine')}, {user.get('location')})")
        places = search_places_for_user(user)
        logger.info(f"Found {len(places)} places for user {user['user_id']}")
        logger.info(f"All fetched place_ids for user {user['user_id']}: {[place.get('id') for place in places]}")

        for place in places:
            place_id = place.get("id")
            if not place_id:
                continue

            logger.info(f"Fetched place_id: {place_id}")

            if already_analyzed(place_id):
                logger.info(f"SKIP: Already analyzed {place_id}")
                continue
            else:
                logger.info(f"NEW: Not yet analyzed {place_id}")

            publish_for_analysis(place_id)
            n_new += 1
    logger.info(f"Done. Published {n_new} new places for analysis.")

if __name__ == "__main__":
    main()
