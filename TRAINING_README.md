# AgriVaidya - Soil Classifier Training Guide

## Overview

The soil classifier in AgriVaidya uses a K-Nearest Neighbors (KNN) approach with HSV histogram features for soil type classification. The training process has been separated from the main application to allow for independent model training and updates.

## Quick Start

### 1. Prepare Your Soil Dataset

Organize your soil images in the following directory structure:

```
AgriVaidya/
├── data/
│   └── Soil Types/
│       ├── Alluvial soil/
│       │   ├── image1.jpg
│       │   ├── image2.jpg
│       │   └── ...
│       ├── Clayey soils/
│       │   ├── image1.jpg
│       │   └── ...
│       ├── Laterite soil/
│       │   └── ...
│       ├── Loamy soil/
│       │   └── ...
│       ├── Sandy loam/
│       │   └── ...
│       └── Sandy soil/
│           └── ...
```

**Supported soil types:**
- Alluvial soil
- Clayey soils
- Laterite soil
- Loamy soil
- Sandy loam
- Sandy soil

### 2. Train the Soil Classifier

Run the training script from the AgriVaidya directory:

```bash
python train_soil.py
```

This will:
- Load all images from the `data/Soil Types/` directory
- Extract HSV histogram features from each image
- Train the KNN classifier
- Save the trained model to `models/soil/`
- Generate statistics about the training data

### 3. Expected Output

```
============================================================
🌾 AgriVaidya Soil Classifier Training
============================================================

📁 Loading training data from: /path/to/data/Soil Types

  🌾 Processing: Alluvial soil
    ✓ Loaded 25 images

  🌾 Processing: Clayey soils
    ✓ Loaded 30 images

  ... (other soil types)

📊 Preparing model data...
✓ Total samples: 157
✓ Soil types: 6
  - Alluvial soil: 25 samples
  - Clayey soils: 30 samples
  ...

💾 Saving model to: /path/to/models/soil

✓ Features saved: soil_features.pkl
✓ Info saved: soil_info.json

============================================================
✅ Training completed successfully!
============================================================

The soil classifier is ready to use.
Model location: /path/to/models/soil
Total training samples: 157
```

## Model Files

The training process generates two files in `models/soil/`:

### 1. `soil_features.pkl`
- Binary pickle file containing extracted features from all training images
- Used by the main app for real-time soil classification
- Format: List of dictionaries with "label" and "features" keys

### 2. `soil_info.json`
- JSON file containing:
  - Training metadata (number of samples per soil type)
  - Soil information and recommendations for each type
  - Total training samples

## How It Works

### Feature Extraction
1. Each soil image is resized to 256×256 pixels
2. Image is converted from BGR to HSV color space
3. HSV histogram is calculated with bins [8, 4, 4] for [H, S, V]
4. Histogram is normalized to create a fixed-size feature vector

### Classification (at runtime)
1. Input soil image features are extracted using the same method
2. K-Nearest Neighbors (K=5) finds the 5 most similar samples in the training set
3. Majority voting determines the predicted soil type
4. Confidence is estimated based on distance to nearest neighbor

### Fallback Behavior
- If no training data is available, the app defaults to "Loamy soil" with 85% confidence
- If the trained model isn't found, the app can use cached features from previous runs
- If all else fails, the app remains functional with default values

## Improving Model Accuracy

### Tips for Better Results

1. **Collect More Samples**
   - Aim for at least 20-30 images per soil type
   - More samples generally improve classification accuracy

2. **Ensure Image Quality**
   - Use consistent lighting conditions
   - Take closeup photos of soil samples
   - Avoid shadows and reflections
   - Ensure clear, well-defined soil characteristics

3. **Standardize Image Conditions**
   - Use same camera or similar camera angles
   - Maintain consistent background
   - Capture soil at the same moisture level for consistency

4. **Include Variety**
   - Capture samples from different angles
   - Include different field locations (if available)
   - Cover seasonal variations if relevant

## Troubleshooting

### No training data loaded
**Error:** "No training data loaded!"
**Solution:** 
- Verify soil images are in `data/Soil Types/` directory
- Check that subdirectories match the expected soil type names exactly
- Ensure images have valid extensions (.jpg, .png, .jpeg, .webp)

### Model not found at runtime
**Error:** "[Soil Classifier] Dataset directory ... not found!"
**Solution:**
- Run `python train_soil.py` first to create the trained model
- Or ensure the `data/Soil Types/` directory exists with training images

### Low confidence predictions
**Cause:** Insufficient or low-quality training data
**Solution:**
- Add more training images per soil type
- Improve image quality and consistency
- Re-run the training script with new data

## Integration with Main App

The main application (`app.py`) automatically handles soil model loading in this order:

1. **Check for pre-trained model** → Load from `models/soil/soil_features.pkl`
2. **Check for cache file** → Load from `data/soil_features_cache.json`
3. **Build from dataset** → If dataset directory exists, extract features on-the-fly
4. **Use default fallback** → If nothing is available, default to "Loamy soil"

## API Endpoint

To use the soil classifier through the API:

```bash
POST /soil/predict
Content-Type: multipart/form-data

image: <binary image data>
```

**Response:**
```json
{
  "soil": "Loamy soil",
  "confidence": "92.5%",
  "description": "The ideal agricultural soil...",
  "crops": "Tomatoes, Peppers, Lettuce, ...",
  "problems": "Can lose nutrients over seasons...",
  "solutions": "Maintain structure by adding..."
}
```

## Model Update Workflow

To update the soil classifier with new training data:

1. Add new soil images to `data/Soil Types/<soil_type>/` directories
2. Run `python train_soil.py` again
3. The trained model in `models/soil/` will be updated
4. Restart the main app to use the new model

---

**Last Updated:** 2024
**Version:** 1.0
