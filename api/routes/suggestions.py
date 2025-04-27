import os
import random
import time
import traceback
from google.cloud import firestore
import requests
from flask import Blueprint, jsonify
from ml.inference import load_model, get_prediction

# ——————————————————————————————————————————————————————————————————
# Blueprints & clients
# ——————————————————————————————————————————————————————————————————
suggestions = Blueprint('suggestions', __name__)
send_all    = Blueprint('send_all', __name__)

db    = firestore.Client()
model = load_model()

# ——————————————————————————————————————————————————————————————————
# Helper: fetch review + summary + priceLevel
# ——————————————————————————————————————————————————————————————————
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
        price_level = data.get("priceLevel", "N/A")

        # pick the longest good review
        filtered = [r for r in reviews if r.get("rating", 0) >= 4 and r.get("text")]
        filtered.sort(key=lambda r: len(r["text"]), reverse=True)
        if filtered:
            return filtered[0]["text"], summary, price_level
        # fallback
        for r in reviews:
            if r.get("text"):
                return r["text"], summary, price_level

    except Exception as e:
        print(f"⚠️ fetch_review_and_details({place_id}) failed: {e}", flush=True)

    return "No review available", summary, price_level

# ——————————————————————————————————————————————————————————————————
# Helper: filter, score, shuffle & update history
# ——————————————————————————————————————————————————————————————————
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

            # photo URL
            photo_url = None
            photos = p.get("photos")
            if photos:
                ref = photos[0].get("name")
                if ref:
                    photo_url = (
                        f"https://places.googleapis.com/v1/{ref}/media"
                        f"?maxHeightPx=400&key={os.environ.get('MAPS_API_KEY')}"
                    )

            # ML score
            try:
                score = get_prediction([float(rating), 1.0], model)
            except:
                score = 0

            if score == 1:
                review, summary, price = fetch_review_and_details(pid)
                out.append({
                    "name":              name,
                    "address":           address,
                    "rating":            rating,
                    "total_reviews":     count,
                    "photo_url":         photo_url,
                    "place_id":          pid,
                    "maps_url":          f"https://www.google.com/maps/place/?q=place_id:{pid}",
                    "save_link":         f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={pid}",
                    "price_level":       price,
                    "generative_summary": summary,
                    "latest_review":     review
                })
        return out

    # first try skipping already‐sent
    suggs = build(False)
    # if none left, allow repeats
    if not suggs and user_id:
        suggs = build(True)

    random.shuffle(suggs)

    # record top‐3 in history
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

# ——————————————————————————————————————————————————————————————————
# Single‐user endpoint
# ——————————————————————————————————————————————————————————————————
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
        "textQuery": text_query,
        "includedType": cuisine_type,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 2500.0}},
        "pageSize": 20
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ.get("MAPS_API_KEY", ""),
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.photos,places.generativeSummary"
    }

    r = requests.post("https://places.googleapis.com/v1/places:searchText", headers=headers, json=payload, timeout=10)
    if r.status_code != 200:
        print(f"❌ Text Search failed ({r.status_code}): {r.text}", flush=True)
        return jsonify({"suggestions": []}), r.status_code

    places = r.json().get("places", [])
    return jsonify({"suggestions": filter_and_format_results(places, user_id=user_id)})

# ——————————————————————————————————————————————————————————————————
# BATCH endpoint
# ——————————————————————————————————————————————————————————————————
@send_all.route('/send_emails_to_all', methods=['POST'])
def send_emails_to_all():
    try:
        errors   = []
        send_url = os.getenv("SEND_EMAIL_URL")
        if not send_url:
            raise RuntimeError("SEND_EMAIL_URL not set")

        print(f"🔄 Batch start → {send_url}", flush=True)
        for doc in db.collection('preferences').stream():
            uid = doc.id
            email = doc.to_dict().get("email")
            if not email:
                errors.append(f"{uid}: no email")
                continue

            url = f"{send_url.rstrip('/')}?user_id={uid}&email={email}"
            print(f"📧 {uid} → {url}", flush=True)
            try:
                resp = requests.get(url, timeout=15)
                print(f"⇢ {uid} status {resp.status_code}", flush=True)
                if resp.status_code not in (200,202):
                    errors.append(f"{uid}: status {resp.status_code}")
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
