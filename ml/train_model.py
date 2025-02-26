import pickle
from sklearn.ensemble import RandomForestClassifier

def train_model(training_data):
    # Dummy training function – training_data should be a list of dicts with 'features' and 'label'
    X = [data['features'] for data in training_data]
    y = [data['label'] for data in training_data]

    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)
    return model

if __name__ == '__main__':
    # Example training data
    training_data = [
        {"features": [4.5, 1.0], "label": 1},
        {"features": [4.3, 1.2], "label": 0},
        {"features": [4.7, 0.8], "label": 1},
    ]
    model = train_model(training_data)
    with open('suggestion_model.pkl', 'wb') as f:
        pickle.dump(model, f)
    print("Model trained and saved as suggestion_model.pkl")
