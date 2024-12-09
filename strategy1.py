import MetaTrader5 as mt5
import pandas as pd
import logging
import time
from datetime import datetime

# Logging setup
logging.basicConfig(
    filename="strategy.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Constants
RSI_PERIOD = 14
EMA_SHORT = 50
EMA_LONG = 200
RISK_PERCENT = 0.02
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

def fetch_data(symbol, timeframe=mt5.TIMEFRAME_H1):
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

def calculate_lot_size(risk_percent, balance):
    """Calculate lot size based on account balance."""
    lot_size = balance * risk_percent / 100000  # Simplified for a 100-pip movement
    min_lot_size = 0.01
    return max(round(lot_size, 2), min_lot_size)

def place_trade(trade_type, symbol, lot_size, entry_price):
    """Place a single trade."""
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if trade_type == "BUY" else tick.bid
    if price is None:
        logging.error(f"Failed to retrieve price for {symbol}.")
        return None

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if trade_type == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": 80,
        "magic": MAGIC_NUMBER,
    }

    logging.info(f"Order request: {request}")
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Failed to place {trade_type} trade for {symbol}.")
        return None

    logging.info(f"Successfully placed {trade_type} trade for {symbol}.")
    return result.order

def analyze_and_trade(symbol, account_info):
    """Analyze market conditions and place trades."""
    data = fetch_data(symbol)
    if data is None:
        return

    current_price = data['close'].iloc[-1]
    ema_50 = data['EMA_50'].iloc[-1]
    ema_200 = data['EMA_200'].iloc[-1]
    rsi = data['RSI'].iloc[-1]

    lot_size = calculate_lot_size(RISK_PERCENT, account_info.balance)

    # Loosened logic for Buy/Sell conditions
    if ema_50 > ema_200 and rsi < 45:
        place_trade("BUY", symbol, lot_size, current_price)
    elif ema_50 < ema_200 and rsi > 55:
        place_trade("SELL", symbol, lot_size, current_price)

    logging.info(f"Trade analyzed for {symbol}: EMA_50={ema_50}, EMA_200={ema_200}, RSI={rsi}.")

def execute_strategy(mt5_settings):
    """Encapsulated strategy execution."""
    if not initialize_mt5(mt5_settings):
        logging.error("Failed to initialize MT5. Exiting.")
        return

    account_info = mt5.account_info()
    if account_info is None:
        logging.error("Failed to retrieve account info.")
        mt5.shutdown()
        return

    try:
        while True:
            logging.info("Starting strategy execution cycle.")
            for symbol in SYMBOLS:
                try:
                    analyze_and_trade(symbol, account_info)
                except Exception as e:
                    logging.error(f"Error in trading loop for {symbol}: {str(e)}")
            logging.info("Cycle complete. Sleeping for 30 seconds.")
            time.sleep(30)
    finally:
        mt5.shutdown()

def main():
    """Main function for the trading script."""
    mt5_settings = {
        "username": 9293182,
        "password": "Ge@mK3Xb",
        "server": "GTCGlobalTrade-Server",
        "mt5Pathway": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
    }
    execute_strategy(mt5_settings)

if __name__ == "__main__":
    main()
