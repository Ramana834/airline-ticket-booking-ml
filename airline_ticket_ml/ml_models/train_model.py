import os
import joblib
import numpy as np
from sklearn.linear_model import LinearRegression

print("ML Training Started...")

# Ensure saved_models folder exists
BASE_DIR = os.path.dirname(__file__)
SAVE_PATH = os.path.join(BASE_DIR, "saved_models")
os.makedirs(SAVE_PATH, exist_ok=True)

# Dummy dataset
X = np.array([[1], [2], [3], [4]])
y = np.array([100, 150, 200, 250])

model_names = [
    "price_model.pkl",
    "delay_model.pkl",
    "demand_model.pkl",
    "recommender.pkl"
]

for name in model_names:
    model = LinearRegression()
    model.fit(X, y)
    joblib.dump(model, os.path.join(SAVE_PATH, name))
    print(f"{name} created")

print("All models trained and saved successfully")
