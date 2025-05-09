#!/usr/bin/env python3
import os
import re
import requests
import argparse
from google.cloud import firestore

# === Configuration ===
MAPS_KEY     = os.environ.get("MAPS_API_KEY")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash-001")
GEMINI_URL   = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"

if not MAPS_KEY or not GEMINI_KEY:
    raise EnvironmentError("❌ Both MAPS_API_KEY and GEMINI_API_KEY must be set in environment.")

print(f"💬 Using Gemini endpoint: '{GEMINI_URL}'")

db = firestore.Client()

# === Helpers ===
def safe_strip(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        nested = value.get("text")
        if isinstance(nested, str):
            return nested.strip()
        print(f"⚠️ Nested 'text' field is not a string: {nested}")
    else:
        print(f"⚠️ Unexpected type for review text: {type(value)} → {value}")
    return ""


def contains_profanity(text):
    profanity_list = ["fuck", "shit", "bitch", "asshole", "bastard"]
    pattern = re.compile(r"\b(" + "|".join(profanity_list) + r")\b", re.IGNORECASE)
    return bool(pattern.search(text))

# === Functions ===
def fetch_reviews(place_id, n=10):
    url = f"https://places.googleapis.com/v1/places/{place_id}?fields=reviews&key={MAPS_KEY}"
    print(f"🔗 Request URL: {url}")
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise Exception(f"Places API Error: {data['error'].get('message', 'Unknown error')}")
    raw = data.get("reviews", [])
    return [ safe_strip(r.get("text", "")) for r in raw ][:n]


def call_gemini(prompt: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":      0.3,
            "candidateCount":   1,
            "maxOutputTokens":  200
        }
    }
    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_KEY}",
        headers={"Content-Type": "application/json; charset=utf-8"},
        json=payload
    )
    resp.raise_for_status()
    data = resp.json()
    candidate = data.get("candidates", [{}])[0]
    if candidate.get("finishReason") == "SAFETY":
        raise Exception("Gemini response blocked for safety reasons.")
    return candidate["content"]["parts"][0].get("text", "").strip()


def analyze(place_id: str):
    print(f"📍 Analyzing {place_id}")
    reviews = fetch_reviews(place_id)
    if not reviews:
        print("⚠️ No reviews found.")
        return

    joined = "\n\n".join(f"- {r}" for r in reviews if r)
    print("📝 Joined reviews:")
    print(joined)
    if contains_profanity(joined):
        print("⚠️ Warning: profanity detected; output may be affected.")

    prompts = {
        "pros_cons":          "Given these reviews, produce two lists titled 'Pros:' and 'Cons:' summarizing **all** reviews.\n\n" + joined,
        "summary":            "Provide a concise, two-sentence summary capturing the restaurant's overall character based on **all** reviews.\n\n" + joined,
        "tags":               "Based on **all** reviews, list comma-separated tags that best describe this place as a whole (e.g. cozy, family-friendly, romantic).\n\n" + joined,
        "recommended_dishes": "From **all** reviews, choose up to three dishes most recommended; return as bullet points.\n\n" + joined,
        "unique_ingredients": "From **all** reviews, list up to three unique ingredients mentioned; if none, return 'nothing mentioned'.\n\n" + joined,
        # Honest one-sentence summary of popularity
        "buzz":               "Based on these reviews, summarize the real-world buzz in one sentence—mention any lines, peak times, booking challenges, or indicators of popularity to give a truthful tip.\n\n" + joined,
        # Focus purely on physical atmosphere
        "ambience":           (
            "In one sentence, describe the restaurant’s **physical atmosphere**—"
            "focusing on lighting, noise level, music, décor style, and overall vibe—"
            "without mentioning the food.\n\n" 
            + joined
        ),
        "instagramm_score":   "Assign one of four categories—'Very High', 'High', 'Medium', or 'Low'—to describe the restaurant’s overall Instagrammability based on **all** reviews.\n\n" + joined,
    }


    result = {
        "pros_cons":          call_gemini(prompts["pros_cons"]),
        "summary":            call_gemini(prompts["summary"]),
        "tags":               [t.strip() for t in call_gemini(prompts["tags"]).split(",") if t.strip()],
        "recommended_dishes": [l.strip() for l in call_gemini(prompts["recommended_dishes"]).split("\n") if l.strip()][:3],
        "unique_ingredients": ( [i.strip() for i in call_gemini(prompts["unique_ingredients"]).split(",") if i.strip()] or ["nothing mentioned"] ),
        "buzz":               call_gemini(prompts["buzz"]),
        "ambience":           call_gemini(prompts["ambience"]),
        "instagramm_score":   call_gemini(prompts["instagramm_score"]),
        "updated":            firestore.SERVER_TIMESTAMP
    }

    print(f"✅ Saving analysis for {place_id}")
    db.collection("place_analysis").document(place_id).set(result)

# === Entry Point ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    place_ids = set()
    for doc in db.collection("history").stream():
        for pid in doc.to_dict().get("place_ids", []):
            if isinstance(pid, str):
                place_ids.add(pid)
            elif isinstance(pid, dict) and "place_id" in pid:
                place_ids.add(pid["place_id"])
    place_ids = list(place_ids)

    print(f"🕵️ Found {len(place_ids)} place(s)")
    for pid in place_ids[: args.limit]:
        try:
            analyze(pid)
        except Exception as e:
            print(f"❌ Error analyzing {pid}: {e}")
