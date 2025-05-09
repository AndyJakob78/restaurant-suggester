import os
import random
import time
import traceback
import logging
from google.cloud import firestore
import requests
from flask import Blueprint, jsonify

# Import the feature fetcher you added in train_user_model.py
from ml.training.train_user_model import fetch_place_features

# Inference helpers
from ml.inference import load_model, get_prediction

# ———— Logging setup ————
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("suggestion")
logger.setLevel(logging.INFO)

# ———— Blueprints & clients ————
suggestions = Blueprint('suggestions', __name__)
send_all    = Blueprint('send_all', __name__)

db    = firestore.Client()
model = load_model()  # Load your trained model at startup

# ———— Helper: fetch review + summary + priceLevel ————
def fetch_review_and_details(place_id):
    api_key = os.environ.get("MAPS_API_KEY")
    url = (
        f"https://places.googleapis.com/v1/places/{place_id}"
        f"?fields=reviews,priceLevel,generativeSummary&key={api_key}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        reviews     = data.get("reviews", [])
        gen_summary = data.get("generativeSummary", {})
        summary = (
            gen_summary.get("description", {}).get("text")
            or gen_summary.get("overview", {}).get("text", "")
        )
        price_level = data.get("priceLevel", "N/A" )

        # pick the longest positive review
        filtered = [r for r in reviews if r.get("rating",0) >= 4 and r.get("text")]
        filtered.sort(key=lambda r: len(r["text"]), reverse=True)
        if filtered:
            return filtered[0]["text"], summary, price_level
        for r in reviews:
            if r.get("text"):
                return r["text"], summary, price_level

    except Exception as e:
        print(f"⚠️ fetch_review_and_details({place_id}) failed: {e}", flush=True)

    return "No review available", summary, price_level

# ———— Helper: filter, score, shuffle & update history ————
def filter_and_format_results(places, user_id=None):
    sent_ids = set()
    if user_id:
        hist = db.collection("history").document(user_id).get()
        if hist.exists:
            sent_ids = set(hist.to_dict().get("place_ids", []))

    def build(skip_history):
        out = []
        for p in places:
            pid = p.get("id")
            if not pid or (not skip_history and pid in sent_ids):
                continue

            name     = p.get("displayName", {}).get("text")
            address  = p.get("formattedAddress")
            rating   = p.get("rating", 0.0)
            count    = p.get("userRatingCount", "N/A")

            photo_url = None
            photos = p.get("photos")
            if photos:
                ref = photos[0].get("name")
                if ref:
                    photo_url = (
                        f"https://places.googleapis.com/v1/{ref}/media"
                        f"?maxHeightPx=400&key={os.environ.get('MAPS_API_KEY')}"
                    )

            # --- NEW: fetch the real features you trained on ---
            feats = fetch_place_features(pid)
            if feats is None:
                # skip places that failed to fetch features
                logger.warning(f"Skipping {pid}: feature fetch failed")
                continue

            # --- Get prediction (0 or 1) from your model ---
            try:
                score = get_prediction(feats, model)
            except Exception as e:
                logger.warning(f"Prediction failed for {pid}: {e}")
                score = 0

            # Only include if predicted "click" (score == 1)
            if score == 1:
                review, summary, price = fetch_review_and_details(pid)
                out.append({
                    "name":               name,
                    "address":            address,
                    "rating":             rating,
                    "total_reviews":      count,
                    "photo_url":          photo_url,
                    "place_id":           pid,
                    "maps_url":           f"https://www.google.com/maps/place/?q=place_id:{pid}",
                    "save_link":          f"https://www.google.com/maps/search/?api=1&query_place_id={pid}",
                    "price_level":        price,
                    "generative_summary": summary,
                    "latest_review":      review
                })
        return out

    # generate suggestions, skipping history first
    suggs = build(False)
    # if no new suggestions, allow repeats
    if not suggs and user_id:
        suggs = build(True)

    logger.debug("Before shuffle: %s", [s["place_id"] for s in suggs])
    random.shuffle(suggs)
    logger.debug("After  shuffle: %s", [s["place_id"] for s in suggs])

    # record top-3 in history
    if user_id and suggs:
        try:
            ref = db.collection("history").document(user_id)
            prev = ref.get()
            old_ids = prev.to_dict().get("place_ids", []) if prev.exists else []
            new_ids = [s["place_id"] for s in suggs[:3]]
            keep = list({*old_ids, *new_ids})[:50]
            ref.set({"place_ids": keep, "last_sent": firestore.SERVER_TIMESTAMP})
        except Exception as e:
            print(f"🚨 history write failed: {e}", flush=True)

    return suggs

# ———— Single-user endpoint ————
@suggestions.route('/suggestions', methods=['GET'])
def no_user():
    return jsonify({"error": "Use /suggestions/<user_id>"}), 400

@suggestions.route('/suggestions/<user_id>', methods=['GET'])
def get_suggestions_for_user(user_id):
    pref = db.collection('preferences').document(user_id).get()
    if not pref.exists:
        return jsonify({"error": "No preferences found."}), 404

    data     = pref.to_dict()
    cuisine  = data.get("cuisine")
    loc      = data.get("location")
    variants = data.get("query_variants", [])

    if not cuisine or not loc:
        return jsonify({"error": "'cuisine' and 'location' required"}), 400

    cuisine_type = cuisine.strip().lower().replace(" ", "_") + "_restaurant"
    lat, lng     = map(float, loc.split(","))
    text_query   = random.choice(variants) if variants else cuisine

    payload = {
        "textQuery":    text_query,
        "includedType": cuisine_type,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 2500.0}},
        "pageSize": 20
    }
    headers = {
        "Content-Type":    "application/json",
        "X-Goog-Api-Key":  os.environ.get("MAPS_API_KEY", ""),
        "X-Goog-FieldMask":"places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.photos,places.generativeSummary"
    }

    # fetch up to 3 pages for more variety
    all_places = []
    next_token = None
    for _ in range(30):
        req_payload = payload.copy()
        if next_token:
            time.sleep(2)
            req_payload["pageToken"] = next_token

        resp = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers,
            json=req_payload,
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"❌ Text Search failed ({resp.status_code}): {resp.text}", flush=True)
            return jsonify({"suggestions": []}), resp.status_code

        data = resp.json()
        all_places.extend(data.get("places", []))
        next_token = data.get("nextPageToken")
        if not next_token:
            break

    # dedupe by place_id
    unique = {p.get("id"): p for p in all_places if p.get("id")}
    places = list(unique.values())

    return jsonify({"suggestions": filter_and_format_results(places, user_id=user_id)})

# ———— BATCH endpoint ————
@send_all.route('/send_emails_to_all', methods=['POST'])
def send_emails_to_all():
    try:
        errors   = []
        send_url = os.getenv("SEND_EMAIL_URL")
        if not send_url:
            raise RuntimeError("SEND_EMAIL_URL not set")

        print(f"🔄 Batch start → {send_url}", flush=True)
        for doc in db.collection('preferences').stream():
            uid   = doc.id
            email = doc.to_dict().get("email")
            if not email:
                errors.append(f"{uid}: no email")
                continue

            resp = requests.get(f"https://{os.getenv('CLOUD_RUN_SERVICE_URL')}/api/suggestions/{uid}")
            if resp.status_code != 200:
                errors.append(f"{uid}: suggestions fetch failed {resp.status_code}")
                continue
            suggs = resp.json().get('suggestions', [])

            params  = {'user_id': uid, 'email': email}
            payload = {'suggestions': suggs}
            print(f"📧 {uid} → sending email", flush=True)
            try:
                r2 = requests.post(send_url, params=params, json=payload, timeout=15)
                print(f"⇢ {uid} email status {r2.status_code}", flush=True)
                if r2.status_code not in (200,202):
                    errors.append(f"{uid}: email status {r2.status_code}")
            except Exception as e:
                tb = traceback.format_exc()
                print(f"❌ {uid} exception:\n{tb}", flush=True)
                errors.append(f"{uid}: {e}")

        status = "partial_success" if errors else "success"
        print(f"✅ Batch done, errors={errors}", flush=True)
        return jsonify({"status": status, "errors": errors}), (207 if errors else 200)

    except Exception:
        tb = traceback.format_exc()
        print(f"🚨 send_emails_to_all crashed:\n{tb}", flush=True)
        return jsonify({"error": "internal"}), 500
