# -*- coding: utf-8 -*-
import os
import pickle
import random
import requests
import logging
from google.cloud import firestore
from google.cloud.storage import Client as StorageClient
from sklearn.ensemble import RandomForestClassifier

# ——————————————————————————————————————————————————————————————————
# Configuration
# ——————————————————————————————————————————————————————————————————
MAPS_API_KEY = os.environ.get("MAPS_API_KEY")
if not MAPS_API_KEY:
    raise RuntimeError("MAPS_API_KEY environment variable is required for feature fetcher.")

MODEL_BUCKET = os.environ.get(
    "MODEL_BUCKET", 
    "restaurant-suggester-452114-models"
)
MODEL_GCS_PATH = "user-pref-model/suggestion_model.pkl"

# ——————————————————————————————————————————————————————————————————
# Helper: fetch numeric features for a place
# ——————————————————————————————————————————————————————————————————
def fetch_place_features(place_id):
    """
    Calls the Google Places Details API to fetch rating and userRatingCount.
    Returns a feature vector [rating, userRatingCount], or None if fetching fails.
    """
    url = (
        f"https://places.googleapis.com/v1/places/{place_id}"
        f"?fields=rating,userRatingCount&key={MAPS_API_KEY}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rating = data.get("rating", 0.0)
        user_rating_count = data.get("userRatingCount", 0)
        return [float(rating), float(user_rating_count)]
    except requests.exceptions.HTTPError as e:
        logging.warning(f"Failed to fetch features for {place_id}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logging.warning(f"Error fetching features for {place_id}: {e}")
        return None

# ——————————————————————————————————————————————————————————————————
# Training logic
# ——————————————————————————————————————————————————————————————————
def train_model(training_data):
    """
    Given a list of {features: [...], label: 0/1}, fit a RandomForestClassifier.
    """
    X = [example['features'] for example in training_data]
    y = [example['label'] for example in training_data]

    clf = RandomForestClassifier(n_estimators=100)
    clf.fit(X, y)
    return clf

# ——————————————————————————————————————————————————————————————————
# Main entry: read feedback from Firestore, train, save and upload to GCS
# ——————————————————————————————————————————————————————————————————
def main():
    db = firestore.Client()

    # 1) Collect positive feedback (clicks)
    feedback_ref = db.collection('feedback')
    training_data = []
    for doc in feedback_ref.stream():
        data = doc.to_dict()
        if data.get('action') != 'click':
            continue
        place_id = data.get('place_id')
        feats = fetch_place_features(place_id)
        if feats is None:
            print(f"⚠️  Skipping {place_id}: failed to fetch features.")
            continue
        training_data.append({'place_id': place_id, 'features': feats, 'label': 1})

    if not training_data:
        print("No click events found; skipping model training.")
        return

    # 2) Negative sampling: pick non-clicked places as negatives
    all_places_ref = db.collection('places')
    all_place_ids = [p.id for p in all_places_ref.stream()]
    clicked_ids = {ex['place_id'] for ex in training_data}
    neg_ids = [pid for pid in all_place_ids if pid not in clicked_ids]
    random.shuffle(neg_ids)
    num_neg = len(training_data)
    for pid in neg_ids[:num_neg]:
        feats = fetch_place_features(pid)
        if feats is None:
            continue
        training_data.append({'place_id': pid, 'features': feats, 'label': 0})

    # 3) Train the model
    model = train_model(training_data)
    local_path = 'suggestion_model.pkl'
    with open(local_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"✅ Model trained on {len(training_data)} examples and saved to {local_path}")

    # 4) Upload to GCS
    storage_client = StorageClient()
    bucket = storage_client.bucket(MODEL_BUCKET)
    blob = bucket.blob(MODEL_GCS_PATH)
    blob.upload_from_filename(local_path)
    print(f"✅ Uploaded model to gs://{MODEL_BUCKET}/{MODEL_GCS_PATH}")

if __name__ == '__main__':
    main()
