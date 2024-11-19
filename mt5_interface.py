import MetaTrader5 as MetaTrader5
import requests
import time
import schedule
import pytz
from datetime import datetime
import os

# Function to initialize MT5
def start_mt5(username, password, server, path):
    uname = str(username) or os.getenv("MT5_USERNAME")
    pword = str(password) or os.getenv("MT5_PASSWORD")
    trading_server = str(server) or os.getenv("MT5_SERVER")
    filepath = str(path)  # MetaTrader 5 executable file path

    # Attempt to start MT5
    if MetaTrader5.initialize(login=uname, password=pword, server=trading_server, path=filepath):
        print("Trading Bot Starting")
        # Login to MT5
        if MetaTrader5.login(login=uname, password=pword, server=trading_server):
            print("Trading Bot Logged in and Ready to Go!")
            return True
        else:
            print("Login Failed:", MetaTrader5.last_error())
            MetaTrader5.shutdown()
            return PermissionError
    else:
        print("MT5 Initialization Failed:", MetaTrader5.last_error())
        return ConnectionAbortedError

# Function to initialize a symbol on MT5
def initialize_symbols(symbol_array):
    # Get a list of all symbols supported in MT5
    all_symbols = MetaTrader5.symbols_get()
    # Create an array to store all the symbols
    symbol_names = []
    # Add the retrieved symbols to the array
    for symbol in all_symbols:
        symbol_names.append(symbol.name)

    # Check each symbol in symbol_array to ensure it exists
    for provided_symbol in symbol_array:
        if provided_symbol in symbol_names:
            # If it exists, enable
            if MetaTrader5.symbol_select(provided_symbol, True):
                print(f"Symbol {provided_symbol} enabled")
            else:
                return ValueError
        else:
            return SyntaxError

    # Return true when all symbols enabled
    return True

# Function to retrieve the last 90 H1 candlestick data
def get_last_90_candles(symbol):
    # Retrieve the last 90 H1 candles for the symbol
    rates = MetaTrader5.copy_rates_from_pos(symbol, MetaTrader5.TIMEFRAME_H1, 0, 90)

    if rates is None or len(rates) == 0:
        print("Failed to retrieve candlestick data.")
        return None

    # Return a list of open, high, low data from the last 90 candles
    return [{'open': rate.open, 'high': rate.high, 'low': rate.low, 'close': rate.close} for rate in rates]

# Function to send data to FastAPI and get prediction
def get_prediction(candle_data):
    url = "http://127.0.0.1:8000/predict"  # Change to actual FastAPI URL
    data = {
        "features": candle_data
    }

    # Send request to FastAPI server
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()['prediction']  # Assuming the prediction is returned in the response
    else:
        print("Failed to get prediction from FastAPI:", response.status_code)
        return None

# Main function to compare prediction with the last candlestick close
def main():
    start_mt5("9293182", "Ge@mK3Xb", "GTCGlobalTrade-Server", "C:\\Program Files\\MetaTrader 5\\terminal64.exe")

    symbol = "EURUSD"  # Example symbol
    last_90_candles = get_last_90_candles(symbol)
    if last_90_candles is None:
        print("Error: Failed to get the last 90 candles.")
        return

    print(f"Last 90 Candles Data: {last_90_candles}")

    # Send data to FastAPI and get the predicted value
    prediction = get_prediction(last_90_candles)

    if prediction is None:
        print("Error: Prediction failed.")
        return

    print(f"Prediction Value: {prediction}")

    # Compare prediction with the most recent close price
    last_close = last_90_candles[-1]['close']
    if prediction > last_close:
        print("Prediction is higher than the last close. Placing Buy Order...")
        place_trade(symbol, "buy")
    else:
        print("Prediction is lower or equal to the last close. Placing Sell Order...")
        place_trade(symbol, "sell")

# Function to place a trade
def place_trade(symbol, order_type):
    lot_size = 0.1  # For example purposes
    price = MetaTrader5.symbol_info_tick(symbol).ask if order_type == "buy" else MetaTrader5.symbol_info_tick(symbol).bid
    stop_loss = 20  # Example stop loss distance (in pips)
    take_profit = 60  # Example take profit distance (in pips)

    # Place the order
    if order_type == "buy":
        ticket = MetaTrader5.order_send(symbol, MetaTrader5.ORDER_TYPE_BUY, lot_size, price, 3, price - stop_loss,
                                        price + take_profit, "Prediction Buy", 0, 0, MetaTrader5.COLOR_BLUE)
    else:
        ticket = MetaTrader5.order_send(symbol, MetaTrader5.ORDER_TYPE_SELL, lot_size, price, 3, price + stop_loss,
                                        price - take_profit, "Prediction Sell", 0, 0, MetaTrader5.COLOR_RED)

    # Check if order is successfully placed
    if ticket < 0:
        print("Error placing order:", MetaTrader5.last_error())
    else:
        print(f"Order placed successfully. Ticket: {ticket}")

# Schedule the main function to run 1 minute after every hour
schedule.every().hour.at(":12").do(main)

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)
