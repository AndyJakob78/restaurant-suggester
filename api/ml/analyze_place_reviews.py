import os
import requests
import argparse
from google.cloud import firestore

# === Configuration ===
MAPS_KEY = os.environ.get("MAPS_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-001:generateContent"

if not MAPS_KEY or not GEMINI_KEY:
    raise EnvironmentError("❌ Both MAPS_API_KEY and GEMINI_API_KEY must be set in environment.")

print(f"MAPS_KEY in full script: '{MAPS_KEY}'")

db = firestore.Client()

# === Functions ===

def fetch_reviews(place_id, n=10):
    url = f"https://places.googleapis.com/v1/places/{place_id}?fields=reviews&key={MAPS_KEY}"
    print(f"Request URL: {url}")
    resp = requests.get(url)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Places API HTTP Error: {e}")
        raise

    data = resp.json()
    if "error" in data:
        raise Exception(f"Places API Error: {data['error'].get('message', 'Unknown error')}")

    # Return up to n reviews, fallback to empty list if reviews are missing
    return [r.get("text", "").strip() for r in data.get("reviews", [])][:n]


def call_gemini(prompt: str):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "candidateCount": 1,
            "maxOutputTokens": 200
        }
    }
    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_KEY}",
        headers={"Content-Type": "application/json; charset=utf-8"},
        json=payload
    )
    resp.raise_for_status()
    response_json = resp.json()

    candidate = response_json.get("candidates", [{}])[0]
    if candidate.get("finishReason") == "SAFETY":
        raise Exception("Gemini response blocked for safety reasons.")

    # Robust fallback for missing content or text
    try:
        return candidate["content"]["parts"][0].get("text", "").strip()
    except (KeyError, IndexError, TypeError):
        print("❌ Gemini API response format unexpected.")
        print(f"📬 Raw JSON: {response_json}")
        raise Exception("Gemini API returned an unexpected structure")


def analyze(place_id):
    place_id = place_id.strip()
    print(f"📍 Analyzing {place_id}")
    try:
        reviews = fetch_reviews(place_id)
        if not reviews:
            print("⚠️ No reviews found.")
            return

        joined = "\n\n".join(f"- {r}" for r in reviews if r)

        prompts = {
            "pros_cons": f"Here are 10 user reviews of a restaurant. Summarize as two lists, 'Pros:' and 'Cons:'\n\n{joined}",
            "tags": f"From these reviews, list comma-separated tags (e.g. cozy, good for couples, family-friendly):\n{joined}",
            "blurb": f"Write a 2-sentence description of the restaurant based on these reviews:\n{joined}"
        }

        analysis = {
            "pros_cons": call_gemini(prompts["pros_cons"]),
            "tags": [t.strip() for t in call_gemini(prompts["tags"]).split(",") if t.strip()],
            "blurb": call_gemini(prompts["blurb"]),
            "updated": firestore.SERVER_TIMESTAMP
        }

        print(f"Firestore write attempt for place_id: {place_id}")
        db.collection("place_analysis").document(place_id).set(analysis)
        print("✅ Analysis saved.")

    except requests.exceptions.HTTPError as e:
        print(f"❌ Failed to analyze {place_id}: Places API HTTP Error - {e}")
        if e.response is not None:
            print(f"Status Code: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
    except Exception as e:
        print(f"❌ Failed to analyze {place_id}: {e}")


# === Entry Point ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    place_ids = set()
    for doc in db.collection("history").stream():
        place_ids.update(doc.to_dict().get("place_ids", []))

    place_ids = list(place_ids)
    print(f"🕵️ Found {len(place_ids)} place(s) total in history.")

    for place_id in place_ids[:args.limit]:
        try:
            analyze(place_id)
        except Exception as e:
            print(f"❌ Failed to analyze {place_id}: {e}")
