import pandas as pd
import numpy as np
import logging
import tracebackfrom tensorflow.keras.models import load_model
from joblib import load
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import os


# set up logging
logging.basicConfig(lovel=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

#load model and scalers
model = load_model("gru_model.h5")
scaler_X = load("X_train_scaled.joblib")
scaler_y = load("y_train_scaled.joblib")

# Define the FastAPI app
app = FastAPI()

#define a request body model
class PredictionRequest(BaseModel):
    features: list #input features in JSON format

@app.post("/predict")
async def predict(request: PredictionRequest):
    try:
        #log the incoming request
        logging.info(f"received request with data: {request.features}")

        #convert input data to DataFrame
        data = pd.DataFrame(request.features, columns=['open', 'high','low'])

        #Ensure data is numeric
        data = data.apply(pd.to_numeric, errors='coerce')

        #features engineering function
        def add_features(data):
            #moving averages
            data['SMA_20'] = data['open'].rolling(window=20).mean()
            data['EMA_50'] = data['open'].ewm(span=50, adjust=False).mean()
            #RSI
            delta = data['open'].diff(1)
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(wondow=14).mean()
            avg_loss = loss.rolling(wondow=14).mean()
            rs = avg_gain / avg_loss
            data['RSI_14'] = 100 -(100 / (1 + rs))
            # MACD
            data['MACD'] = data['open'].ewm(span=12, adjust=False).mean() - data['open'].ewm(span=26, adjust=False).mean()
            #volatility
            data['volatility_20'] = data['open'].pct_change().rolling(window=20).std()
            return data

        # apply feature engineering
        data = add_features(data)

        #drop rows with NaN values(caused by rolling calculations)
        data = data.dropna()

        #check if data is empty after dropna
        if data.empty:
            raise ValueError("data is empty after feature engineering. Not enough data points")

        #scale the incoming features
        scaled_data = scaler_X.transform(data)

        #reshape the features for model input
        time_steps = 90

        #ensure we are using the last data
        scaled_data = scaled_data[-210:]

        #reshape the data
        reshaped_data = scaled_data.reshape((1, timestep, scaled_data.shape[1]))
        # make the prediction and inverse scale the result
        prediction_scaled = model.predict(reshaped_data)
        prediction = scaler_y.inverse_transform(prediction_scaled)

        # checking if there are multiple predictions
        if prediction.shape[0] > 1:
            prediction_value = prediction[0, -2:].tolist()
        else:
            prediction_value = prediction[0].tolist()

        #log the prediction before returning
        logging.info(f"prediction: {prediction_value}")
        return{"prediction": prediction_value}

    except Exception as e:
        logging.error(f"Error occurred: {str(e)}")
        logging.error(traceback.format_exc())



            