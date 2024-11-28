import MetaTrader5 as MetaTrader5
import requests
import time
import schedule
import pytz
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(
    filename="trading_bot.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Function to initialize MT5
def start_mt5(username, password, server, path):
    uname = int(username) or os.getenv("MT5_USERNAME")
    pword = str(password) or os.getenv("MT5_PASSWORD")
    trading_server = str(server) or os.getenv("MT5_SERVER")
    filepath = str(path)  # MetaTrader 5 executable file path

    logging.info("Initializing MT5...")
    if MetaTrader5.initialize(login=uname, password=pword, server=trading_server, path=filepath):
        logging.info("Trading Bot Starting")
        if MetaTrader5.login(login=uname, password=pword, server=trading_server):
            logging.info("Trading Bot Logged in and Ready to Go!")
            return True
        else:
            error = MetaTrader5.last_error()
            logging.error(f"Login Failed: {error}")
            MetaTrader5.shutdown()
            return PermissionError
    else:
        error = MetaTrader5.last_error()
        logging.error(f"MT5 Initialization Failed: {error}")
        return ConnectionAbortedError

# Function to initialize a symbol on MT5
def initialize_symbols(symbol_array):
    logging.info("Initializing symbols...")
    all_symbols = MetaTrader5.symbols_get()
    symbol_names = [symbol.name for symbol in all_symbols]

    for provided_symbol in symbol_array:
        if provided_symbol in symbol_names:
            if MetaTrader5.symbol_select(provided_symbol, True):
                logging.info(f"Symbol {provided_symbol} enabled")
            else:
                logging.error(f"Failed to enable symbol: {provided_symbol}")
                return ValueError
        else:
            logging.error(f"Symbol {provided_symbol} not found in MT5")
            return SyntaxError

    logging.info("All symbols initialized successfully.")
    return True

def get_last_90_candles(symbol):
    """Retrieve the last 90 H1 candlestick data."""
    logging.info(f"Retrieving last 90 H1 candles for symbol: {symbol}")
    rates = MetaTrader5.copy_rates_from_pos(symbol, MetaTrader5.TIMEFRAME_H1, 0, 720)

    if rates is None or len(rates) == 0:
        logging.error("Failed to retrieve candlestick data.")
        return None

    logging.info("Candlestick data retrieved successfully.")
    return [
        {'open': rate['open'], 'high': rate['high'], 'low': rate['low'], 'close': rate['close']}
        for rate in rates
    ]

# Function to send data to FastAPI and get prediction
def get_prediction(candle_data):
    url = "http://127.0.0.1:8000/predict"  # Change to actual FastAPI URL
    data = {"features": candle_data}
    logging.info("Sending data to FastAPI for prediction...")

    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            logging.info("Prediction received successfully.")
            return response.json()['prediction']
        else:
            logging.error(f"Failed to get prediction from FastAPI. Status Code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error during FastAPI request: {e}")
        return None

# Main function to compare prediction with the last candlestick close
def main():
    logging.info("Starting main trading function...")
    start_status = start_mt5("9293182", "Ge@mK3Xb", "GTCGlobalTrade-Server", "C:\\Program Files\\MetaTrader 5\\terminal64.exe")
    if start_status is not True:
        logging.error("MT5 failed to start.")
        return

    symbol = "EURUSD"  # Example symbol
    last_90_candles = get_last_90_candles(symbol)
    if last_90_candles is None:
        logging.error("Failed to get the last 90 candles.")
        return

    logging.debug(f"Last 90 Candles Data: {last_90_candles}")
    prediction = get_prediction(last_90_candles)

    if prediction is None:
        logging.error("Prediction failed.")
        return

    logging.info(f"Prediction Value: {prediction}")
    last_close = last_90_candles[-1]['close']
    if prediction > last_close:
        logging.info("Prediction is higher than the last close. Placing Buy Order...")
        place_trade(symbol, "buy")
    else:
        logging.info("Prediction is lower or equal to the last close. Placing Sell Order...")
        place_trade(symbol, "sell")

# Function to place a trade
def place_trade(symbol, order_type):
    lot_size = 0.1
    price = MetaTrader5.symbol_info_tick(symbol).ask if order_type == "buy" else MetaTrader5.symbol_info_tick(symbol).bid
    stop_loss = 120  # Example stop loss distance (in pips)
    take_profit = 360  # Example take profit distance (in pips)

    logging.info(f"Placing {order_type.upper()} order for {symbol}.")
    try:
        if order_type == "buy":
            ticket = MetaTrader5.order_send(symbol, MetaTrader5.ORDER_TYPE_BUY, lot_size, price, 3, price - stop_loss,
                                            price + take_profit, "Prediction Buy", 0, 0, MetaTrader5.COLOR_BLUE)
        else:
            ticket = MetaTrader5.order_send(symbol, MetaTrader5.ORDER_TYPE_SELL, lot_size, price, 3, price + stop_loss,
                                            price - take_profit, "Prediction Sell", 0, 0, MetaTrader5.COLOR_RED)

        if ticket < 0:
            logging.error(f"Error placing order: {MetaTrader5.last_error()}")
        else:
            logging.info(f"Order placed successfully. Ticket: {ticket}")
    except Exception as e:
        logging.error(f"Error during order placement: {e}")

# Schedule the main function to run 1 minute after every hour
schedule.every().hour.at(":59").do(main)

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)
