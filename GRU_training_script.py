import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import joblib
import logging
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import GRU, Dense
from keras.callbacks import EarlyStopping
import schedule
import time
from datetime import datetime

# Logging setup
logging.basicConfig(
    filename="forex_model_training.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# MetaTrader 5 settings
MT5_SETTINGS = {
    "login": 9293182,
    "password": "Ge@mK3Xb",
    "server": "GTCGlobalTrade-Server",
    "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}

# Constants
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H4
START_DATE = datetime(2020, 1, 1)
END_DATE = datetime(2024, 12, 22)
TIMESTEPS = 90  # Number of timesteps for sequence modeling

# Function to initialize MetaTrader 5
def initialize_mt5():
    if not mt5.initialize(
        login=MT5_SETTINGS["login"],
        password=MT5_SETTINGS["password"],
        server=MT5_SETTINGS["server"],
        path=MT5_SETTINGS["path"]
    ):
        logging.error("Failed to initialize MT5")
        raise ConnectionError("MT5 initialization failed.")
    logging.info("MT5 initialized successfully.")

# Fetch candlestick data
def fetch_candlestick_data(symbol, timeframe, start_date, end_date):
    utc_start = int(start_date.timestamp())
    utc_end = int(end_date.timestamp())
    rates = mt5.copy_rates_range(symbol, timeframe, utc_start, utc_end)
    if rates is None:
        logging.error(f"Failed to fetch data for {symbol}")
        raise ValueError(f"Could not fetch data for {symbol}")
    data = pd.DataFrame(rates)
    data["time"] = pd.to_datetime(data["time"], unit="s")
    return data

# Preprocess data
def preprocess_data(data):
    data.columns = map(str.lower, data.columns)  # Change column case to lower
    data = data.drop_duplicates()  # Drop duplicates
    data = data.set_index("time").sort_index()  # Sort by time
    data = data.interpolate(method="linear")  # Fill missing values
    return data

# Feature engineering
def feature_engineering(data):
    data["sma_50"] = data["close"].rolling(window=50).mean()  # 50-period SMA
    data["sma_200"] = data["close"].rolling(window=200).mean()  # 200-period SMA
    data["rsi"] = compute_rsi(data["close"], period=14)  # RSI
    data["macd"], data["signal"] = compute_macd(data["close"])  # MACD
    data["target"] = data["close"].shift(-1)  # Target is the next close price
    data = data.dropna()  # Drop rows with NaN values
    return data

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(series, short=12, long=26, signal=9):
    short_ema = series.ewm(span=short, adjust=False).mean()
    long_ema = series.ewm(span=long, adjust=False).mean()
    macd = short_ema - long_ema
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

# Create sequences for GRU input
def create_sequences(data, timesteps):
    X, y = [], []
    for i in range(len(data) - timesteps):
        X.append(data[i:i + timesteps, :-1])  # All columns except target
        y.append(data[i + timesteps, -1])  # Target column
    return np.array(X), np.array(y)

# Build and train GRU model
def train_gru_model(X_train, y_train, X_val, y_val):
    model = Sequential([
        GRU(64, activation="tanh", return_sequences=True, input_shape=(TIMESTEPS, X_train.shape[2])),
        GRU(32, activation="tanh"),
        Dense(1)
    ])
    model.compile(optimizer="adam", loss="mse")
    early_stop = EarlyStopping(monitor="val_loss", patience=10)
    model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=100, batch_size=32, callbacks=[early_stop])
    return model

# Save scalers and model
def save_scalers_and_model(X_scaler, y_scaler, model):
    joblib.dump(X_scaler, "X_train_scaled.joblib")
    joblib.dump(y_scaler, "y_train_scaled.joblib")
    model.save("gru_model.h5")

# Automated weekly process
def automate_training():
    logging.info("Starting weekly automated training process.")
    try:
        initialize_mt5()
        data = fetch_candlestick_data(SYMBOL, TIMEFRAME, START_DATE, END_DATE)
        data = preprocess_data(data)
        data = feature_engineering(data)

        # Split data
        X = data.drop(columns=["target"]).values
        y = data["target"].values.reshape(-1, 1)

        X_scaler = MinMaxScaler()
        y_scaler = MinMaxScaler()
        X_scaled = X_scaler.fit_transform(X)
        y_scaled = y_scaler.fit_transform(y)

        X_sequences, y_sequences = create_sequences(np.hstack((X_scaled, y_scaled)), TIMESTEPS)

        # Split into training, validation, and test sets
        X_train, X_temp, y_train, y_temp = train_test_split(X_sequences, y_sequences, test_size=0.3, shuffle=False)
        X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, shuffle=False)

        # Train GRU model
        model = train_gru_model(X_train, y_train, X_val, y_val)

        # Save scalers and model
        save_scalers_and_model(X_scaler, y_scaler, model)
        logging.info("Training and saving completed successfully.")
    except Exception as e:
        logging.error(f"Error in training process: {e}")
    finally:
        mt5.shutdown()

# Schedule the task weekly
schedule.every().week.do(automate_training)

# Run the automation
if __name__ == "__main__":
    logging.info("Starting script.")
    automate_training()  # Run once initially
    while True:
        schedule.run_pending()
        time.sleep(1)
