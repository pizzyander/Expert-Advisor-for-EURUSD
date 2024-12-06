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
        logging.info("Prediction is higher than the last close. Placing Buy Order with Programmatic TP...")
        place_trade_with_programmatic_tp(symbol, "buy")
    else:
        logging.info("Prediction is lower or equal to the last close. Placing Sell Order with Programmatic TP...")
        place_trade_with_programmatic_tp(symbol, "sell")


def place_trade_with_programmatic_tp(symbol, order_type):
    lot_size = 0.3  # Total lot size to trade
    price = (
        MetaTrader5.symbol_info_tick(symbol).ask
        if order_type == "buy"
        else MetaTrader5.symbol_info_tick(symbol).bid
    )
    point = MetaTrader5.symbol_info(symbol).point  # Point value for the symbol
    tp_levels = [
        price + (120 * point) if order_type == "buy" else price - (120 * point),
        price + (240 * point) if order_type == "buy" else price - (240 * point),
        price + (360 * point) if order_type == "buy" else price - (360 * point),
    ]
    tp_lot_sizes = [0.1, 0.1, 0.1]  # Partial lot sizes for each take-profit level

    logging.info(f"Placing {order_type.upper()} order for {symbol}.")
    try:
        # Place the initial trade
        request = {
            "action": MetaTrader5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": MetaTrader5.ORDER_TYPE_BUY if order_type == "buy" else MetaTrader5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 10,
            "magic": 123456,
            "comment": "Programmatic TP",
            "type_time": MetaTrader5.ORDER_TIME_GTC,
            "type_filling": MetaTrader5.ORDER_FILLING_IOC,
        }

        result = MetaTrader5.order_send(request)

        if result.retcode != MetaTrader5.TRADE_RETCODE_DONE:
            logging.error(f"Initial order placement failed: {result.retcode}")
            return
        else:
            logging.info(f"Initial order placed successfully. Ticket: {result.order}")

        # Monitor the price and close portions of the trade at TP levels
        ticket = result.order
        for i, tp in enumerate(tp_levels):
            logging.info(f"Waiting for price to reach TP Level {i+1} ({tp}).")
            while True:
                current_price = (
                    MetaTrader5.symbol_info_tick(symbol).bid
                    if order_type == "buy"
                    else MetaTrader5.symbol_info_tick(symbol).ask
                )

                # Check if the price has reached the TP level
                if (order_type == "buy" and current_price >= tp) or (
                    order_type == "sell" and current_price <= tp
                ):
                    logging.info(f"Price reached TP Level {i+1}. Closing {tp_lot_sizes[i]} lots.")
                    
                    # Close the portion of the trade
                    close_request = {
                        "action": MetaTrader5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": tp_lot_sizes[i],
                        "type": MetaTrader5.ORDER_TYPE_SELL if order_type == "buy" else MetaTrader5.ORDER_TYPE_BUY,
                        "position": ticket,  # Reference the initial position
                        "price": current_price,
                        "deviation": 10,
                        "magic": 123456,
                        "comment": f"TP Level {i+1} closure",
                        "type_time": MetaTrader5.ORDER_TIME_GTC,
                        "type_filling": MetaTrader5.ORDER_FILLING_IOC,
                    }

                    close_result = MetaTrader5.order_send(close_request)

                    if close_result.retcode != MetaTrader5.TRADE_RETCODE_DONE:
                        logging.error(f"Failed to close portion at TP Level {i+1}: {close_result.retcode}")
                    else:
                        logging.info(f"Successfully closed {tp_lot_sizes[i]} lots at TP Level {i+1}.")
                    break  # Exit loop and move to the next TP level

                time.sleep(1)  # Check price every second

    except Exception as e:
        logging.error(f"Error during trade placement or TP management: {e}")

# Schedule the main function to run 1 minute after every hour
schedule.every().hour.at(":22").do(main)

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)
