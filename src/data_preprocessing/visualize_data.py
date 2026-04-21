import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def visualize(df):
    print("\n📊 Generating Visualizations...")

    # Crop distribution
    plt.figure(figsize=(12, 6))
    sns.countplot(x='label', data=df)
    plt.xticks(rotation=90)
    plt.title("Crop Distribution")
    plt.tight_layout()
    plt.show()

    # Correlation heatmap
    plt.figure(figsize=(10, 8))
    sns.heatmap(df.corr(), annot=True, cmap='coolwarm')
    plt.title("Feature Correlation Heatmap")
    plt.show()

    # Histograms
    df.hist(figsize=(12, 10))
    plt.suptitle("Feature Distributions")
    plt.show()


if __name__ == "__main__":
    path = os.path.join(BASE_DIR, "dataset/processed/cleaned_crop_data.csv")
    df = pd.read_csv(path)

    visualize(df)