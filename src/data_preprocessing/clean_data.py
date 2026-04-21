import pandas as pd
import os

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def clean_data(df):
    print("\n🔍 Checking Missing Values:\n")
    print(df.isnull().sum())

    # Fill missing numeric values
    df.fillna(df.mean(numeric_only=True), inplace=True)

    # Remove duplicates
    df = df.drop_duplicates()

    print("\n✅ Data Cleaned Successfully")
    print("New Shape:", df.shape)

    return df


def save_clean_data(df):
    output_path = os.path.join(BASE_DIR, "dataset/processed/cleaned_crop_data.csv")
    df.to_csv(output_path, index=False)
    print("\n💾 Cleaned data saved at:", output_path)


if __name__ == "__main__":
    input_path = os.path.join(BASE_DIR, "dataset/crop/Crop_recommendation.csv")

    df = pd.read_csv(input_path)
    df = clean_data(df)
    save_clean_data(df)