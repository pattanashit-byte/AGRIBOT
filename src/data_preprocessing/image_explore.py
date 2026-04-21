import os
import matplotlib.pyplot as plt
import cv2

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def explore_images():
    dataset_path = os.path.join(BASE_DIR, "dataset/disease/plantvillage dataset/color")

    print("\n📁 Disease Classes:\n")

    folders = os.listdir(dataset_path)

    for folder in folders:
        print("➡️", folder)

    # Show one sample image
    first_class = folders[0]
    class_path = os.path.join(dataset_path, first_class)

    first_image = os.listdir(class_path)[0]
    image_path = os.path.join(class_path, first_image)

    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    plt.imshow(img)
    plt.title(first_class)
    plt.axis('off')
    plt.show()


if __name__ == "__main__":
    explore_images()