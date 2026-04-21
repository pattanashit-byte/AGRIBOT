import pandas as pd
from sklearn.model_selection import train_test_split
import os

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def split_data(df):
    X = df.drop('label', axis=1)
    y = df['label']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print("\n✅ Data Split Completed")
    print("X_train:", X_train.shape)
    print("X_test:", X_test.shape)

    return X_train, X_test, y_train, y_test


if __name__ == "__main__":
    path = os.path.join(BASE_DIR, "dataset/processed/cleaned_crop_data.csv")
    df = pd.read_csv(path)

    split_data(df)