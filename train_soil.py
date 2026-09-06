#!/usr/bin/env python3
"""
AgriVaidya Soil Classifier Training Script
===========================================

This script trains the soil classifier independently from the main app.
It extracts features from soil images and saves a trained model to:
    models/soil/soil_features.pkl
    models/soil/soil_info.json

Usage:
    python train_soil.py

Make sure you have the soil dataset in:
    data/Soil Types/
        ├── Alluvial soil/
        ├── Clayey soils/
        ├── Laterite soil/
        └── ... (other soil types)
"""

import cv2
import json
import pickle
import numpy as np
from pathlib import Path
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "Soil Types"
MODEL_DIR = BASE_DIR / "models" / "soil"
FEATURES_FILE = MODEL_DIR / "soil_features.pkl"
INFO_FILE = MODEL_DIR / "soil_info.json"

# Soil information and recommendations
SOIL_INFO = {
    "Alluvial soil": {
        "description": "Fine-grained fertile soil formed by deposits from river flows. Highly rich in potash and phosphoric acid, but poor in nitrogen.",
        "crops": "Rice, Wheat, Sugarcane, Cotton, Jute, Maize, Oilseeds",
        "problems": "Compaction under heavy machinery, prone to waterlogging in low-lying areas, and nutrient depletion (specifically Nitrogen).",
        "solutions": "Implement balanced NPK fertilization, practice crop rotation (legumes to restore Nitrogen), and install proper field drainage systems."
    },
    "Clayey soils": {
        "description": "Heavy soil with extremely fine mineral particles. It retains moisture very well but suffers from slow water drainage and poor aeration.",
        "crops": "Rice, Wheat, Gram, Sugarcane, Broccoli, Cabbage",
        "problems": "High density leads to compaction, sticky when wet, extremely hard and cracked when dry, leading to root suffocation.",
        "solutions": "Add organic matter (compost, manure) to improve structure. Avoid working/tilling the soil when wet. Apply gypsum to aggregate clay particles."
    },
    "Laterite soil": {
        "description": "Highly leached red-colored soil rich in iron and aluminum oxides, typical of wet tropical areas. Highly acidic with low nutrient content.",
        "crops": "Cashew nuts, Tea, Coffee, Rubber, Coconut, Ragi",
        "problems": "High acidity leaches essential nutrients, extremely low organic matter/humus content, poor moisture retention.",
        "solutions": "Apply agricultural lime (calcium carbonate) to neutralize acidity. Incorporate organic compost and green manures heavily to restore nutrients."
    },
    "Loamy soil": {
        "description": "The ideal agricultural soil. A balanced mix of sand, silt, and clay. Retains moisture while draining well, aerates easily, and is rich in nutrients.",
        "crops": "Tomatoes, Peppers, Lettuce, Carrots, Wheat, Sugarcane, Fruit Trees",
        "problems": "Can lose nutrients over seasons of intensive farming; vulnerable to topsoil erosion if left bare.",
        "solutions": "Maintain structure by adding light compost annually, use mulch to conserve surface moisture, and apply cover crops in off-seasons."
    },
    "Sandy loam": {
        "description": "A light soil consisting of sand with small amounts of silt and clay. Warms up quickly in spring, provides excellent drainage, and is very easy to work.",
        "crops": "Potatoes, Carrots, Onions, Tomatoes, Melons, Strawberries",
        "problems": "Moderate nutrient leaching and dries out faster than true loamy soil during dry spells.",
        "solutions": "Perform regular organic matter additions to increase water-holding capacity, use mulching, and split fertilizer applications into smaller, frequent doses."
    },
    "Sandy soil": {
        "description": "Coarse-textured soil with large particles. It has rapid drainage, virtually no nutrient retention capacity, and dries out extremely fast.",
        "crops": "Carrots, Radishes, Peanuts, Watermelons, Asparagus, Lavender",
        "problems": "High rate of nutrient leaching, extremely low moisture retention, highly susceptible to wind and water erosion.",
        "solutions": "Incorporate massive amounts of organic compost or composted manure, grow winter cover crops, use drip irrigation, and apply organic mulch."
    }
}


# ============================================================================
# FUNCTIONS
# ============================================================================

def extract_soil_features(img):
    """
    Extract HSV histogram features from a soil image.
    
    Args:
        img: OpenCV image (BGR format)
        
    Returns:
        Normalized feature vector (flattened histogram)
    """
    if img is None:
        return None
    
    # Resize for consistent feature extraction
    img_resized = cv2.resize(img, (256, 256))
    
    # Convert to HSV color space
    hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    
    # Calculate histogram
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
    
    # Normalize histogram
    cv2.normalize(hist, hist)
    
    return hist.flatten()


def load_training_data():
    """
    Load all soil images and extract features.
    
    Returns:
        Dictionary with soil types as keys and lists of feature vectors as values
    """
    training_data = defaultdict(list)
    
    if not DATA_DIR.exists():
        print(f"❌ Dataset directory not found: {DATA_DIR}")
        return None
    
    print(f"📁 Loading training data from: {DATA_DIR}")
    
    for soil_type_dir in DATA_DIR.iterdir():
        if not soil_type_dir.is_dir():
            continue
        
        soil_type = soil_type_dir.name
        print(f"\n  🌾 Processing: {soil_type}")
        
        image_count = 0
        for img_file in soil_type_dir.glob("*"):
            if img_file.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
                continue
            
            try:
                img = cv2.imread(str(img_file))
                if img is None:
                    continue
                
                features = extract_soil_features(img)
                if features is not None:
                    training_data[soil_type].append(features)
                    image_count += 1
                    
            except Exception as e:
                print(f"    ⚠️  Error processing {img_file.name}: {e}")
                continue
        
        if image_count > 0:
            print(f"    ✓ Loaded {image_count} images")
        else:
            print(f"    ⚠️  No valid images found")
    
    if not training_data:
        print("\n❌ No training data loaded!")
        return None
    
    return training_data


def train_model(training_data):
    """
    Prepare training data for KNN-based soil classification.
    
    Args:
        training_data: Dictionary with soil types and feature vectors
        
    Returns:
        Tuple of (soil_features_list, metadata)
    """
    soil_features = []
    metadata = {
        "soil_types": list(training_data.keys()),
        "sample_counts": {},
        "total_samples": 0
    }
    
    print("\n📊 Preparing model data...")
    
    for soil_type, features_list in training_data.items():
        for features in features_list:
            soil_features.append({
                "label": soil_type,
                "features": features.tolist()
            })
        
        metadata["sample_counts"][soil_type] = len(features_list)
        metadata["total_samples"] += len(features_list)
    
    print(f"✓ Total samples: {metadata['total_samples']}")
    print(f"✓ Soil types: {len(metadata['soil_types'])}")
    
    for soil_type, count in metadata["sample_counts"].items():
        print(f"  - {soil_type}: {count} samples")
    
    return soil_features, metadata


def save_model(soil_features, metadata):
    """
    Save trained model to disk.
    
    Args:
        soil_features: List of feature dictionaries
        metadata: Training metadata
    """
    # Create model directory
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Saving model to: {MODEL_DIR}")
    
    # Save features using pickle
    try:
        with open(FEATURES_FILE, 'wb') as f:
            pickle.dump(soil_features, f)
        print(f"✓ Features saved: {FEATURES_FILE.name}")
    except Exception as e:
        print(f"❌ Error saving features: {e}")
        return False
    
    # Save soil info and metadata
    try:
        model_data = {
            "metadata": metadata,
            "soil_info": SOIL_INFO
        }
        with open(INFO_FILE, 'w') as f:
            json.dump(model_data, f, indent=2)
        print(f"✓ Info saved: {INFO_FILE.name}")
    except Exception as e:
        print(f"❌ Error saving info: {e}")
        return False
    
    return True


def main():
    """Main training pipeline"""
    print("\n" + "="*60)
    print("🌾 AgriVaidya Soil Classifier Training")
    print("="*60)
    
    # Load training data
    training_data = load_training_data()
    if not training_data:
        print("\n❌ Training failed: No training data available")
        return False
    
    # Train model
    soil_features, metadata = train_model(training_data)
    
    # Save model
    if save_model(soil_features, metadata):
        print("\n" + "="*60)
        print("✅ Training completed successfully!")
        print("="*60)
        print(f"\nThe soil classifier is ready to use.")
        print(f"Model location: {MODEL_DIR}")
        print(f"Total training samples: {metadata['total_samples']}")
        return True
    else:
        print("\n❌ Failed to save model")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
