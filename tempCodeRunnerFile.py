import MetaTrader5 as mt5
import requests
import time
import schedule
import os

# Function to initialize MT5
def start_mt5(username, password, server, path):
    uname = int("9293182") 
    pword = str("Ge@mK3Xb") 
    trading_server = str("GTCGlobalTrade-Server") 
    filepath = str("C:\\Users\\PIZZY\\Downloads\\mt5setup.exe")  # MetaTrader 5 executable file path

    # Attempt to start MT5
    if mt5.initialize(login=uname, password=pword, server=trading_server, path=filepath):
        print("Trading Bot Starting")
        # Login to MT5
        if mt5.login(login=uname, password=pword, server=trading_server):
            print("Trading Bot Logged in and Ready to Go!")
            return True
        else:
            print("Login Failed:", mt5.last_error())
            mt5.shutdown()
            return False
    else:
        print("MT5 Initialization Failed:", mt5.last_error())
        return False

# Function to get the last 90 candles
def get_last_90_candles(symbol):
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to activate symbol: {symbol}")
        return None
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 480)
    if rates is None:
        print(f"Failed to retrieve rates for {symbol}.")
        return None
    # Convert rates to a list of dictionaries
    return [{'open': rate['open'], 'high': rate['high'], 'low': rate['low'], 'close': rate['close']} for rate in rates]

# Function to send data to FastAPI and get prediction
def get_prediction(candle_data):
    url = "http://127.0.0.1:8000/predict"  # Change to actual FastAPI URL
    data = {
        "features": candle_data
    }

    try:
        response = requests.post(url, json=data, timeout=10)  # Adding timeout to avoid blocking
        if response.status_code == 200:
            return response.json()['prediction']  # Assuming the prediction is returned in the response
        else:
            print("Failed to get prediction from FastAPI:", response.status_code)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None


# Function to place a trade
def place_trade(symbol, order_type):
    lot_size = 0.10  # For example purposes

    # Get the current market price (ask for buy, bid for sell)
    price = mt5.symbol_info_tick(symbol).ask if order_type == "buy" else mt5.symbol_info_tick(symbol).bid

    # Define stop loss and take profit distances (in pips)
    stop_loss_pips = 40  # Example stop loss distance (in pips)
    take_profit_pips = 80  # Example take profit distance (in pips)

    # Convert pips to price points (1 pip = 0.0001 for EUR/USD)
    stop_loss = price - stop_loss_pips * mt5.symbol_info(
        symbol).point if order_type == "buy" else price + stop_loss_pips * mt5.symbol_info(symbol).point
    take_profit = price + take_profit_pips * mt5.symbol_info(
        symbol).point if order_type == "buy" else price - take_profit_pips * mt5.symbol_info(symbol).point

    # Get minimum stop level for the symbol
    min_stop_level = mt5.symbol_info(symbol).trade_stops_level

    # Check if stop loss and take profit are beyond the minimum stop level
    if abs(stop_loss - price) < min_stop_level * mt5.symbol_info(symbol).point or abs(
            take_profit - price) < min_stop_level * mt5.symbol_info(symbol).point:
        print(
            f"Error: Stop loss or take profit is too close to the execution price. Minimum stop level is {min_stop_level} pips.")
        return

    # Create the order request
    request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': lot_size,
        'type': mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
        'price': price,
        'sl': stop_loss,  # Set the stop loss with respect to the execution price
        'tp': take_profit,  # Set the take profit with respect to the execution price
        'deviation': 10,
        'magic': 234000,  # Just an example magic number
        'comment': f"Prediction {order_type.capitalize()}",
        'type_filling': mt5.ORDER_FILLING_IOC,
        'type_time': mt5.ORDER_TIME_GTC
    }

    # Send the order
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("Error placing order:", result)
    else:
        print(f"Order placed successfully. Ticket: {result.order}")


# Main function to compare prediction with the last candlestick close
def main():
    if not start_mt5("9293182", "Ge@mK3Xb", "GTCGlobalTrade-Server", "C:\\Program Files\\MetaTrader 5\\terminal64.exe"):
        return

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
    if prediction < last_close:
        print("Prediction is higher than the last close. Placing Buy Order...")
        place_trade(symbol, "buy")
    else:
        print("Prediction is lower or equal to the last close. Placing Sell Order...")
        place_trade(symbol, "sell")

# Schedule the main function to run 1 minute after every hour
schedule.every().hour.at(":05").do(main)

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)
