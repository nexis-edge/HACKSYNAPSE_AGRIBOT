"""Runtime soil-classification service used by the Flask application.

Training remains in ``train_soil.py``. This module only loads its exported
model and turns an OpenCV image into a soil prediction.
"""

import json
import pickle
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "data" / "Soil Types"
MODEL_DIR = BASE_DIR / "models" / "soil"
FEATURES_FILE = MODEL_DIR / "soil_features.pkl"
INFO_FILE = MODEL_DIR / "soil_info.json"
CACHE_FILE = BASE_DIR / "data" / "soil_features_cache.json"

DEFAULT_SOIL = "Loamy soil"
SOIL_INFO = {
    "Alluvial soil": {
        "description": "Fine-grained fertile soil formed by deposits from river flows. Highly rich in potash and phosphoric acid, but poor in nitrogen.",
        "crops": "Rice, Wheat, Sugarcane, Cotton, Jute, Maize, Oilseeds",
        "problems": "Compaction under heavy machinery, prone to waterlogging in low-lying areas, and nutrient depletion (specifically Nitrogen).",
        "solutions": "Implement balanced NPK fertilization, practice crop rotation (legumes to restore Nitrogen), and install proper field drainage systems.",
    },
    "Clayey soils": {
        "description": "Heavy soil with extremely fine mineral particles. It retains moisture very well but suffers from slow water drainage and poor aeration.",
        "crops": "Rice, Wheat, Gram, Sugarcane, Broccoli, Cabbage",
        "problems": "High density leads to compaction, sticky when wet, extremely hard and cracked when dry, leading to root suffocation.",
        "solutions": "Add organic matter (compost, manure) to improve structure. Avoid working/tilling the soil when wet. Apply gypsum to aggregate clay particles.",
    },
    "Laterite soil": {
        "description": "Highly leached red-colored soil rich in iron and aluminum oxides, typical of wet tropical areas. Highly acidic with low nutrient content.",
        "crops": "Cashew nuts, Tea, Coffee, Rubber, Coconut, Ragi",
        "problems": "High acidity leaches essential nutrients, extremely low organic matter/humus content, poor moisture retention.",
        "solutions": "Apply agricultural lime (calcium carbonate) to neutralize acidity. Incorporate organic compost and green manures heavily to restore nutrients.",
    },
    "Loamy soil": {
        "description": "The ideal agricultural soil. A balanced mix of sand, silt, and clay. Retains moisture while draining well, aerates easily, and is rich in nutrients.",
        "crops": "Tomatoes, Peppers, Lettuce, Carrots, Wheat, Sugarcane, Fruit Trees",
        "problems": "Can lose nutrients over seasons of intensive farming; vulnerable to topsoil erosion if left bare.",
        "solutions": "Maintain structure by adding light compost annually, use mulch to conserve surface moisture, and apply cover crops in off-seasons.",
    },
    "Sandy loam": {
        "description": "A light soil consisting of sand with small amounts of silt and clay. Warms up quickly in spring, provides excellent drainage, and is very easy to work.",
        "crops": "Potatoes, Carrots, Onions, Tomatoes, Melons, Strawberries",
        "problems": "Moderate nutrient leaching and dries out faster than true loamy soil during dry spells.",
        "solutions": "Perform regular organic matter additions to increase water-holding capacity, use mulching, and split fertilizer applications into smaller, frequent doses.",
    },
    "Sandy soil": {
        "description": "Coarse-textured soil with large particles. It has rapid drainage, virtually no nutrient retention capacity, and dries out extremely fast.",
        "crops": "Carrots, Radishes, Peanuts, Watermelons, Asparagus, Lavender",
        "problems": "High rate of nutrient leaching, extremely low moisture retention, highly susceptible to wind and water erosion.",
        "solutions": "Incorporate massive amounts of organic compost or composted manure, grow winter cover crops, use drip irrigation, and apply organic mulch.",
    },
}


def extract_soil_features(image):
    """Return a normalized HSV histogram for an OpenCV BGR image."""
    if image is None:
        return None

    resized = cv2.resize(image, (256, 256))
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
    cv2.normalize(histogram, histogram)
    return histogram.flatten()


class SoilClassifier:
    """Loads the saved KNN feature vectors and classifies soil images."""

    def __init__(self):
        self.features = []
        self.soil_info = SOIL_INFO.copy()
        self.load_model()

    def load_model(self):
        """Load trained features, with legacy cache/dataset fallbacks."""
        self._load_soil_info()
        for source, loader in (
            (FEATURES_FILE, self._load_pickle_features),
            (CACHE_FILE, self._load_json_features),
        ):
            if source.exists() and loader(source):
                print(f"[Soil Classifier] Loaded {len(self.features)} features from {source}")
                return

        self._build_legacy_cache()

    def _load_soil_info(self):
        if not INFO_FILE.exists():
            return
        try:
            with INFO_FILE.open(encoding="utf-8") as info_file:
                self.soil_info.update(json.load(info_file).get("soil_info", {}))
        except (OSError, ValueError) as error:
            print(f"[Soil Classifier] Could not load soil info: {error}")

    def _load_pickle_features(self, path):
        try:
            with path.open("rb") as model_file:
                saved_features = pickle.load(model_file)
            self.features = self._deserialize_features(saved_features)
            return bool(self.features)
        except (OSError, pickle.UnpicklingError, ValueError, TypeError) as error:
            print(f"[Soil Classifier] Could not load trained model: {error}")
            return False

    def _load_json_features(self, path):
        try:
            with path.open(encoding="utf-8") as cache_file:
                self.features = self._deserialize_features(json.load(cache_file))
            return bool(self.features)
        except (OSError, ValueError, TypeError) as error:
            print(f"[Soil Classifier] Could not load feature cache: {error}")
            return False

    @staticmethod
    def _deserialize_features(saved_features):
        return [
            (item["label"], np.asarray(item["features"], dtype=np.float32))
            for item in saved_features
            if item.get("label") and item.get("features") is not None
        ]

    def _build_legacy_cache(self):
        if not DATASET_DIR.exists():
            print("[Soil Classifier] No model available. Run 'python train_soil.py' to train one.")
            return

        cached_features = []
        for soil_dir in DATASET_DIR.iterdir():
            if not soil_dir.is_dir() or soil_dir.name not in self.soil_info:
                continue
            for image_path in soil_dir.iterdir():
                if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                    continue
                features = extract_soil_features(cv2.imread(str(image_path)))
                if features is not None:
                    self.features.append((soil_dir.name, features))
                    cached_features.append({"label": soil_dir.name, "features": features.tolist()})

        if cached_features:
            try:
                CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with CACHE_FILE.open("w", encoding="utf-8") as cache_file:
                    json.dump(cached_features, cache_file)
                print(f"[Soil Classifier] Built cache with {len(self.features)} features.")
            except OSError as error:
                print(f"[Soil Classifier] Could not save feature cache: {error}")

    def predict(self, image):
        """Return soil prediction details for an OpenCV BGR image."""
        input_features = extract_soil_features(image)
        if input_features is None or not self.features:
            soil_type, confidence = DEFAULT_SOIL, 85.0
        else:
            distances = sorted(
                (float(np.linalg.norm(input_features - features)), label)
                for label, features in self.features
            )
            nearest = distances[:5]
            votes = {}
            for distance, label in nearest:
                votes[label] = votes.get(label, 0) + 1
            soil_type = max(votes, key=lambda label: (votes[label], -next(distance for distance, item in distances if item == label)))
            confidence = round(max(55.0, min(99.0, (1.0 - distances[0][0] / 1.5) * 100.0)), 1)

        info = self.soil_info.get(soil_type, self.soil_info[DEFAULT_SOIL])
        return {
            "soil": soil_type,
            "confidence": f"{confidence}%",
            "description": info["description"],
            "crops": info["crops"],
            "problems": info["problems"],
            "solutions": info["solutions"],
        }
