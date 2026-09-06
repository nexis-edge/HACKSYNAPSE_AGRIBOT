import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# ==========================================
# 1. Load dataset
# ==========================================

DATASET = "agri_training_data.csv"

df = pd.read_csv(DATASET)

print("\n===================================")
print("       AgriBot MODEL TRAINING")
print("===================================\n")

print("Dataset shape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

# ==========================================
# 2. Define input features and target
# ==========================================

FEATURES = [
    "N",
    "P",
    "K",
    "pH",
    "temperature",
    "humidity",
    "moisture"
]

TARGET = "crop"

X = df[FEATURES]
y = df[TARGET]

# ==========================================
# 3. Split dataset
# ==========================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("\nTraining samples:", len(X_train))
print("Testing samples :", len(X_test))

# ==========================================
# 4. Create model
# ==========================================

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=12,
    random_state=42,
    class_weight="balanced"
)

# ==========================================
# 5. Train
# ==========================================

print("\nTraining model...")

model.fit(X_train, y_train)

print("Training completed.")

# ==========================================
# 6. Evaluate
# ==========================================

predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

print("\n===================================")
print("MODEL PERFORMANCE")
print("===================================")

print("Accuracy:", round(accuracy * 100, 2), "%")

print("\nClassification Report:")
print(classification_report(y_test, predictions))

# ==========================================
# 7. Feature importance
# ==========================================

print("\nFeature Importance:")

for feature, importance in zip(
    FEATURES,
    model.feature_importances_
):
    print(
        f"{feature:15} : "
        f"{importance:.4f}"
    )

# ==========================================
# 8. Save model
# ==========================================

MODEL_FILE = "agribot_crop_model.pkl"

joblib.dump(
    {
        "model": model,
        "features": FEATURES
    },
    MODEL_FILE
)

print("\nModel saved as:")
print(MODEL_FILE)

print("\nTraining pipeline completed successfully.")