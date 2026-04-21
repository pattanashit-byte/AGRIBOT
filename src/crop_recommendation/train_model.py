import pandas as pd
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def train_crop_model():
    # Load cleaned data
    data_path = os.path.join(BASE_DIR, "dataset/processed/cleaned_crop_data.csv")
    df = pd.read_csv(data_path)

    # Features and target
    X = df.drop("label", axis=1)
    y = df["label"]

    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42
    )

    # Train model
    model = XGBClassifier(use_label_encoder=False, eval_metric='mlogloss')
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print("\n✅ Crop Model Trained")
    print("Accuracy:", acc)

    # Save model
    model_path = os.path.join(BASE_DIR, "models/saved_model/crop_model.pkl")
    encoder_path = os.path.join(BASE_DIR, "models/saved_model/label_encoder.pkl")

    joblib.dump(model, model_path)
    joblib.dump(le, encoder_path)

    print("💾 Model saved at:", model_path)


if __name__ == "__main__":
    train_crop_model()