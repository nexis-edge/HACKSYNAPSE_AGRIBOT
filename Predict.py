import joblib
import pandas as pd

# Load trained model
data = joblib.load("agribot_crop_model.pkl")

model = data["model"]
features = data["features"]

# ==========================================
# Sensor values
# Replace these with Raspberry Pi readings
# ==========================================

sensor_data = {
    "N": 80,
    "P": 45,
    "K": 40,
    "pH": 6.5,
    "temperature": 27,
    "humidity": 65,
    "moisture": 55
}

input_data = pd.DataFrame(
    [sensor_data],
    columns=features
)

# ==========================================
# Prediction
# ==========================================

prediction = model.predict(input_data)

print("\n===================================")
print("          AgriBot PREDICTION")
print("===================================")

print("Recommended Crop:", prediction[0])

# Probability
probabilities = model.predict_proba(input_data)[0]

print("\nCrop probabilities:")

for crop, probability in zip(
    model.classes_,
    probabilities
):
    print(
        f"{crop:15} "
        f"{probability * 100:.2f}%"
    )