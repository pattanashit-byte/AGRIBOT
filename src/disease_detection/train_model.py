import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense
import os

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def train_disease_model():
    dataset_path = os.path.join(BASE_DIR, "dataset/disease/plantvillage dataset/color")

    img_size = (128, 128)
    batch_size = 32

    datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)

    train_data = datagen.flow_from_directory(
        dataset_path,
        target_size=img_size,
        batch_size=batch_size,
        subset='training'
    )

    val_data = datagen.flow_from_directory(
        dataset_path,
        target_size=img_size,
        batch_size=batch_size,
        subset='validation'
    )

    model = Sequential([
        Conv2D(32, (3,3), activation='relu', input_shape=(128,128,3)),
        MaxPooling2D(2,2),
        Conv2D(64, (3,3), activation='relu'),
        MaxPooling2D(2,2),
        Flatten(),
        Dense(128, activation='relu'),
        Dense(train_data.num_classes, activation='softmax')
    ])

    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

    model.fit(train_data, validation_data=val_data, epochs=5)

    model_path = os.path.join(BASE_DIR, "models/saved_model/disease_model.h5")
    model.save(model_path)

    print("\n✅ Disease Model Saved at:", model_path)


if __name__ == "__main__":
    train_disease_model()