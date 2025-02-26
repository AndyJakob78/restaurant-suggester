import pickle

def load_model(model_path='suggestion_model.pkl'):
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    return model

def get_prediction(features, model):
    # Features: list or numpy array
    prediction = model.predict([features])
    return prediction[0]

if __name__ == '__main__':
    model = load_model()
    features = [4.6, 1.0]  # Example features
    prediction = get_prediction(features, model)
    print("Prediction:", prediction)
