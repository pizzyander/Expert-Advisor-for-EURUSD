import pandas as pd
import numpy as np
import logging
import traceback
from tensorflow.keras.models import load_model
from joblib import load
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import os
import uvicorn
import os
import shutil

cache_dir = os.path.join(os.path.dirname(__file__), "__pycache__")
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

# Set up logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Load model and scalers
model = load_model("gru_model.h5")
scaler_X = load("X_train_scaled.joblib")
scaler_y = load("y_train_scaled.joblib")

# Define the FastAPI app
app = FastAPI()

# Define a request body model
class PredictionRequest(BaseModel):
    features: list  # Input features in JSON format

@app.post("/predict")
async def predict(request: PredictionRequest):
    try:
        # Log the incoming request
        logging.info(f"Received request with data: {request.features}")

        # Convert input data to DataFrame
        data = pd.DataFrame(request.features, columns=['open', 'high', 'low'])

        # Ensure data is numeric
        data = data.apply(pd.to_numeric, errors='coerce')

        # Feature Engineering function
        def add_features(data):
            # Moving Averages
            data['SMA_20'] = data['open'].rolling(window=20).mean()
            data['EMA_50'] = data['open'].ewm(span=50, adjust=False).mean()
            # RSI
            delta = data['open'].diff(1)
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            data['RSI_14'] = 100 - (100 / (1 + rs))
            # MACD
            data['MACD'] = data['open'].ewm(span=12, adjust=False).mean() - data['open'].ewm(span=26, adjust=False).mean()
            data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
            # Volatility
            data['volatility_20'] = data['open'].pct_change().rolling(window=20).std()
            return data

        # Apply feature engineering
        data = add_features(data)

        # Drop any rows with NaN values (if caused by rolling calculations)
        data = data.dropna()

        # Check if data is empty after dropna
        if data.empty:
            raise ValueError("Data is empty after feature engineering. Not enough data points.")

        # Scale the incoming features
        scaled_data = scaler_X.transform(data)

        # Reshape for model input (e.g., (1, time_steps, n_features))
        time_steps = 90

        # Ensure we are using the last 90 time steps
        scaled_data = scaled_data[-90:]

        print(f"Shape of scaled_data: {scaled_data.shape}")

        reshaped_data = scaled_data.reshape((1, time_steps, scaled_data.shape[1]))

        # Make prediction and inverse scale the result
        prediction_scaled = model.predict(reshaped_data)
        prediction = scaler_y.inverse_transform(prediction_scaled)

        # If you want to get the last two predicted values
        if prediction.shape[0] > 1:
            # Assuming prediction[0] is the batch, and you're extracting the last two values of the prediction
            prediction_value = prediction[0, -2:].tolist()  # Get the last 2 values from the prediction array
        else:
            # If your prediction is just one value, you can't extract two values, handle accordingly
            prediction_value = prediction[0].tolist()

        # Log the prediction before returning
        logging.info(f"Prediction: {prediction_value}")

        return {"prediction": prediction_value}

    except Exception as e:
        logging.error(f"Error occurred: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Server Error")
