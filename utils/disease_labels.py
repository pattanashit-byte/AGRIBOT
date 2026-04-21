import os
import re


BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"
DISEASE_DATASET_DIR = os.path.join(
    BASE_DIR,
    "dataset",
    "disease",
    "plantvillage dataset",
    "color",
)

PLANT_DISPLAY_OVERRIDES = {
    "Cherry_(including_sour)": "Cherry",
    "Corn_(maize)": "Corn (Maize)",
    "Pepper,_bell": "Bell Pepper",
}

PLANT_ALIASES = {
    "mongo": "mung bean",
    "moong": "mung bean",
    "mung": "mung bean",
    "mungbean": "mung bean",
    "green gram": "mung bean",
}


def load_disease_labels():
    if not os.path.isdir(DISEASE_DATASET_DIR):
        return []

    return sorted(
        name
        for name in os.listdir(DISEASE_DATASET_DIR)
        if os.path.isdir(os.path.join(DISEASE_DATASET_DIR, name))
    )


def format_disease_label(raw_label):
    if not raw_label:
        return "Unknown disease"

    plant, separator, disease = raw_label.partition("___")
    clean_plant = format_plant_name(plant)

    if not separator:
        return clean_plant

    clean_disease = " ".join(disease.replace("_", " ").split())

    if clean_disease.lower() == "healthy":
        return f"{clean_plant} Healthy"

    return f"{clean_plant} - {clean_disease}"


def get_disease_name(class_index):
    if 0 <= class_index < len(DISEASE_LABELS):
        return format_disease_label(DISEASE_LABELS[class_index])

    return f"Unknown disease ({class_index})"


def extract_raw_plant_name(raw_label):
    return raw_label.partition("___")[0]


def normalize_plant_name(plant_name):
    normalized = re.sub(r"[^a-z0-9]+", " ", (plant_name or "").lower()).strip()
    return PLANT_ALIASES.get(normalized, normalized)


def format_plant_name(raw_plant_name):
    if raw_plant_name in PLANT_DISPLAY_OVERRIDES:
        return PLANT_DISPLAY_OVERRIDES[raw_plant_name]

    return " ".join(raw_plant_name.replace("_", " ").split())


def get_supported_plants():
    return sorted(SUPPORTED_PLANTS.values())


def get_supported_plant_options():
    return [
        {"value": plant_key, "label": label}
        for plant_key, label in sorted(SUPPORTED_PLANTS.items(), key=lambda item: item[1])
    ]


def resolve_plant_key(plant_name):
    normalized_name = normalize_plant_name(plant_name)

    if normalized_name in SUPPORTED_PLANTS:
        return normalized_name

    return DISPLAY_NAME_TO_KEY.get(normalized_name)


def get_plant_display_name(plant_name):
    plant_key = resolve_plant_key(plant_name)
    if not plant_key:
        return format_plant_name(plant_name or "Unknown Plant")

    return SUPPORTED_PLANTS[plant_key]


def is_supported_plant(plant_name):
    return resolve_plant_key(plant_name) is not None


def is_healthy_label(raw_label):
    return raw_label.lower().endswith("healthy")


def get_best_disease_for_plant(prediction_scores, plant_name):
    plant_key = resolve_plant_key(plant_name)
    label_indexes = PLANT_TO_LABEL_INDEXES.get(plant_key, [])

    if not label_indexes:
        return None

    best_index = max(label_indexes, key=lambda index: float(prediction_scores[index]))
    return format_disease_label(DISEASE_LABELS[best_index])


def get_plant_prediction_summary(prediction_scores, plant_name):
    plant_key = resolve_plant_key(plant_name)
    label_indexes = PLANT_TO_LABEL_INDEXES.get(plant_key, [])

    if not label_indexes:
        return None

    ranked_indexes = sorted(
        label_indexes,
        key=lambda index: float(prediction_scores[index]),
        reverse=True,
    )
    best_index = ranked_indexes[0]
    disease_indexes = [index for index in ranked_indexes if not is_healthy_label(DISEASE_LABELS[index])]
    healthy_indexes = [index for index in ranked_indexes if is_healthy_label(DISEASE_LABELS[index])]
    top_disease_index = disease_indexes[0] if disease_indexes else None
    top_healthy_index = healthy_indexes[0] if healthy_indexes else None

    return {
        "plant_key": plant_key,
        "plant_label": SUPPORTED_PLANTS[plant_key],
        "best_name": format_disease_label(DISEASE_LABELS[best_index]),
        "best_score": float(prediction_scores[best_index]),
        "best_is_healthy": is_healthy_label(DISEASE_LABELS[best_index]),
        "top_disease_name": format_disease_label(DISEASE_LABELS[top_disease_index]) if top_disease_index is not None else None,
        "top_disease_score": float(prediction_scores[top_disease_index]) if top_disease_index is not None else 0.0,
        "top_healthy_name": format_disease_label(DISEASE_LABELS[top_healthy_index]) if top_healthy_index is not None else None,
        "top_healthy_score": float(prediction_scores[top_healthy_index]) if top_healthy_index is not None else 0.0,
        "has_disease_classes": bool(disease_indexes),
    }


DISEASE_LABELS = load_disease_labels()
SUPPORTED_PLANTS = {}
PLANT_TO_LABEL_INDEXES = {}
DISPLAY_NAME_TO_KEY = {}

for index, label in enumerate(DISEASE_LABELS):
    raw_plant_name = extract_raw_plant_name(label)
    plant_key = normalize_plant_name(raw_plant_name)
    display_label = format_plant_name(raw_plant_name)
    SUPPORTED_PLANTS[plant_key] = display_label
    PLANT_TO_LABEL_INDEXES.setdefault(plant_key, []).append(index)
    DISPLAY_NAME_TO_KEY[normalize_plant_name(display_label)] = plant_key
