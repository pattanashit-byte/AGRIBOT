import pandas as pd
import os

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def load_crop_data():
    file_path = os.path.join(BASE_DIR, "dataset/crop/Crop_recommendation.csv")

    df = pd.read_csv(file_path)

    print("\n✅ Dataset Loaded Successfully")
    print(df.head())
    print("\n📊 Shape:", df.shape)

    return df


if __name__ == "__main__":
    load_crop_data()