import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import joblib
import logging
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from keras.models import Sequential
from keras.layers import GRU, Dense
from keras.callbacks import EarlyStopping
from datetime import datetime
import schedule
import time

# Logging setup
logging.basicConfig(
    filename="forex_model_training.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

class ForexModelTrainer:
    def __init__(self):
        self.MT5_SETTINGS = {
            "login": 9293182,
            "password": "Ge@mK3Xb",
            "server": "GTCGlobalTrade-Server",
            "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
        }
        self.SYMBOL = "EURUSD"
        self.TIMEFRAME = mt5.TIMEFRAME_H1
        self.START_DATE = datetime(2020, 1, 1)
        self.END_DATE = datetime(2024, 12, 22)
        self.TIMESTEPS = 90
        self.X_scaler = MinMaxScaler()
        self.y_scaler = MinMaxScaler()
        self.model = None

    def initialize_mt5(self):
        if not mt5.initialize(
            login=self.MT5_SETTINGS["login"],
            password=self.MT5_SETTINGS["password"],
            server=self.MT5_SETTINGS["server"],
            path=self.MT5_SETTINGS["path"]
        ):
            logging.error("Failed to initialize MT5")
            raise ConnectionError("MT5 initialization failed.")
        logging.info("MT5 initialized successfully.")

    def fetch_candlestick_data(self):
        utc_start = int(self.START_DATE.timestamp())
        utc_end = int(self.END_DATE.timestamp())
        rates = mt5.copy_rates_range(self.SYMBOL, self.TIMEFRAME, utc_start, utc_end)
        if rates is None:
            logging.error(f"Failed to fetch data for {self.SYMBOL}")
            raise ValueError(f"Could not fetch data for {self.SYMBOL}")
        data = pd.DataFrame(rates)
        data["time"] = pd.to_datetime(data["time"], unit="s")
        return data

    def preprocess_data(self, data):
        data.columns = map(str.lower, data.columns)
        data = data.drop_duplicates()
        data = data.set_index("time").sort_index()
        data = data.interpolate(method="linear")
        return data

    def compute_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def compute_macd(self, series, short=12, long=26, signal=9):
        short_ema = series.ewm(span=short, adjust=False).mean()
        long_ema = series.ewm(span=long, adjust=False).mean()
        macd = short_ema - long_ema
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def feature_engineering(self, data):
        data["sma_50"] = data["close"].rolling(window=50).mean()
        data["sma_200"] = data["close"].rolling(window=200).mean()
        data["rsi"] = self.compute_rsi(data["close"], period=14)
        data["macd"], data["signal"] = self.compute_macd(data["close"])
        data["target"] = data["close"].shift(-1)
        data = data.dropna()
        return data

    def create_sequences(self, data):
        X, y = [], []
        for i in range(len(data) - self.TIMESTEPS):
            X.append(data[i:i + self.TIMESTEPS, :-1])
            y.append(data[i + self.TIMESTEPS, -1])
        return np.array(X), np.array(y)

    def train_gru_model(self, X_train, y_train, X_val, y_val):
        model = Sequential([
        GRU(64, activation="tanh", return_sequences=True, input_shape=(self.TIMESTEPS, X_train.shape[2])),
        GRU(32, activation="tanh"),
        Dense(1)
        ])
        model.compile(optimizer="adam", loss="MeanSquaredError")
    
        # Modify the early stopping patience to 5
        early_stop = EarlyStopping(monitor="val_loss", patience=4)

    # Train the model with early stopping
        model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=100, batch_size=32, callbacks=[early_stop])
        return model


    def evaluate_model(self, X_test, y_test):
        """
        Evaluates the model's performance on the test dataset.
        """
        predictions = self.model.predict(X_test)

        # Inverse transform predictions and actual values
        y_test_original = self.y_scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
        predictions_original = self.y_scaler.inverse_transform(predictions).flatten()

        # Calculate evaluation metrics
        mse = mean_squared_error(y_test_original, predictions_original)
        mae = mean_absolute_error(y_test_original, predictions_original)
        r2 = r2_score(y_test_original, predictions_original)

        # Log and print results
        logging.info("Model Evaluation Results:")
        logging.info(f"Mean Squared Error (MSE): {mse:.4f}")
        logging.info(f"Mean Absolute Error (MAE): {mae:.4f}")
        logging.info(f"R-Squared (R²): {r2:.4f}")

        print("Model Evaluation Results:")
        print(f"Mean Squared Error (MSE): {mse:.4f}")
        print(f"Mean Absolute Error (MAE): {mae:.4f}")
        print(f"R-Squared (R²): {r2:.4f}")

    def save_scalers_and_model(self):
        joblib.dump(self.X_scaler, "X_train_scaled.joblib")
        joblib.dump(self.y_scaler, "y_train_scaled.joblib")
        self.model.save("gru_model.keras")
        logging.info("Model and scalers saved successfully.")

    def train_model(self):
        logging.info("Starting weekly automated training process.")
        try:
            self.initialize_mt5()
            data = self.fetch_candlestick_data()
            data = self.preprocess_data(data)
            data = self.feature_engineering(data)

            # Prepare data for training
            X = data.drop(columns=["target"]).values
            y = data["target"].values.reshape(-1, 1)
            X_scaled = self.X_scaler.fit_transform(X)
            y_scaled = self.y_scaler.fit_transform(y)

            X_sequences, y_sequences = self.create_sequences(np.hstack((X_scaled, y_scaled)))

            # Split into training, validation, and test sets
            X_train, X_temp, y_train, y_temp = train_test_split(X_sequences, y_sequences, test_size=0.3, shuffle=False)
            X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, shuffle=False)

            # Train the model
            self.model = self.train_gru_model(X_train, y_train, X_val, y_val)

            # Evaluate the model
            self.evaluate_model(X_test, y_test)

            # Save model and scalers
            self.save_scalers_and_model()

            logging.info("Training, evaluation, and saving completed successfully.")
        except Exception as e:
            logging.error(f"Error in training process: {e}")
        finally:
            mt5.shutdown()

# Automated scheduling
def run_scheduler():
    trainer = ForexModelTrainer()
    trainer.train_model()  # Run once initially
    schedule.every().week.do(trainer.train_model)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    logging.info("Starting script.")
    run_scheduler()
