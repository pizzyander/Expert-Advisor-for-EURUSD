import MetaTrader5 as mt5
import pandas as pd
import logging
import time
import schedule
from datetime import datetime

# Logging setup
logging.basicConfig(
    filename="strategy.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Initialize MT5 with your credentials 
settings = {
    "username": 9293182,
    "password": "Ge@mK3Xb",
    "server": "GTCGlobalTrade-Server",
    "mt5Pathway": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}

# Constants
RSI_PERIOD = 14
EMA_SHORT = 50
EMA_LONG = 200
RISK_PERCENT = 0.1
MAGIC_NUMBER = 456000
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
PIP_VALUES = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.01}

def initialize_mt5(settings):
    """Initialize MetaTrader 5 connection."""
    if not mt5.initialize(
        login=settings["username"],
        password=settings["password"],
        server=settings["server"],
        path=settings["mt5Pathway"],
    ):
        logging.error("MT5 initialization failed.")
        return False
    logging.info("MT5 initialized successfully.")
    return True
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

def fetch_data(symbol, timeframe=mt5.TIMEFRAME_H4):
    """Fetch historical data and calculate indicators."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
    if rates is None or len(rates) == 0:
        logging.error(f"Failed to fetch data for {symbol}.")
        return None

    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s')

    # Calculate RSI
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # Calculate EMAs
    data['EMA_50'] = data['close'].ewm(span=EMA_SHORT).mean()
    data['EMA_200'] = data['close'].ewm(span=EMA_LONG).mean()

    return data

def place_trade_with_programmatic_tp(symbol, order_type, lot_size=0.3):
    """Place a single trade with programmatic take-profit management."""
    # Get the latest market price dynamically
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logging.error(f"Failed to get market tick for {symbol}.")
        return
    
    price = tick.ask if order_type.lower() == "buy" else tick.bid
    point = mt5.symbol_info(symbol).point  # Point value for the symbol
    deviation = 100  # Increased deviation for better flexibility

    # Set take profit levels
    tp_levels = [
        price + (120 * point) if order_type.lower() == "buy" else price - (120 * point),
        price + (240 * point) if order_type.lower() == "buy" else price - (240 * point),
        price + (360 * point) if order_type.lower() == "buy" else price - (360 * point),
    ]
    
    tp_lot_sizes = [0.1, 0.1, 0.1]  # Partial lot sizes for each take-profit level

    logging.info(f"Placing {order_type.upper()} order for {symbol} at price {price}.")
    try:
        # Place the initial trade
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": mt5.ORDER_TYPE_BUY if order_type.lower() == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": deviation,
            "magic": MAGIC_NUMBER,
            "comment": "Programmatic TP",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Initial order placement failed: {result.retcode}")
            return
        else:
            logging.info(f"Initial order placed successfully. Ticket: {result.order}")

        # Monitor the price and close portions of the trade at TP levels
        ticket = result.order
        for i, tp in enumerate(tp_levels):
            logging.info(f"Waiting for price to reach TP Level {i+1} ({tp}).")
            while True:
                current_price = tick.ask if order_type.lower() == "buy" else tick.bid

                if (order_type.lower() == "buy" and current_price >= tp) or (
                    order_type.lower() == "sell" and current_price <= tp
                ):
                    logging.info(f"Price reached TP Level {i+1}. Closing {tp_lot_sizes[i]} lots.")
                    
                    # Close the portion of the trade
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": tp_lot_sizes[i],
                        "type": mt5.ORDER_TYPE_SELL if order_type.lower() == "buy" else mt5.ORDER_TYPE_BUY,
                        "position": ticket,
                        "price": current_price,
                        "deviation": deviation,
                        "magic": MAGIC_NUMBER,
                        "comment": f"TP Level {i+1} closure",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }

                    close_result = mt5.order_send(close_request)

                    if close_result.retcode != mt5.TRADE_RETCODE_DONE:
                        logging.error(f"Failed to close portion at TP Level {i+1}: {close_result.retcode}")
                    else:
                        logging.info(f"Successfully closed {tp_lot_sizes[i]} lots at TP Level {i+1}.")
                    break  # Exit loop and move to the next TP level

                time.sleep(1)  # Check price every second

    except Exception as e:
        logging.error(f"Error during trade placement or TP management: {e}")

# Function to calculate lot size
def calculate_lot_size(risk_percent, balance):
    """Calculate lot size based on account balance and risk percentage."""
    # Assume risk percentage is for a 100-pip move, for simplicity
    lot_size = (balance * risk_percent) / 100000  # Simplified for 100-pip movement
    min_lot_size = 0.01  # Minimum lot size
    return max(round(lot_size, 2), min_lot_size)

def main():
    for symbol in SYMBOLS:
        logging.info(f"Processing {symbol}")
        
        # Fetch the market data for the symbol
        data = fetch_data(symbol)
        
        if data is not None:
            # You can implement your strategy here, for example:
            # - RSI and EMA crossovers
            # - Buy or Sell signal generation
            rsi = data['RSI'].iloc[-1]
            ema_50 = data['EMA_50'].iloc[-1]
            ema_200 = data['EMA_200'].iloc[-1]
            
            # Example strategy: Buy when RSI < 30 and EMA50 crosses above EMA200
            if rsi < 30 and ema_50 > ema_200:
                balance = mt5.account_info().balance
                lot_size = calculate_lot_size(RISK_PERCENT, balance)
                place_trade_with_programmatic_tp(symbol, "buy", lot_size)
                
            # Example strategy: Sell when RSI > 70 and EMA50 crosses below EMA200
            elif rsi > 70 and ema_50 < ema_200:
                balance = mt5.account_info().balance
                lot_size = calculate_lot_size(RISK_PERCENT, balance)
                place_trade_with_programmatic_tp(symbol, "sell", lot_size)
        else:
            logging.error(f"Failed to fetch data for {symbol}")

# Schedule the main function to run every 1 minute
schedule.every(1).minutes.do(main)

if initialize_mt5(settings):
    # Keep the script running and executing the scheduled tasks
    while True:
        schedule.run_pending()
        time.sleep(1)
else:
    logging.error("MT5 initialization failed. Exiting script.")
