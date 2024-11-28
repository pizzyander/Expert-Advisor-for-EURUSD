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
DEVIATION = 100  # Fixed deviation
LOT_SIZE = 0.1  # Fixed lot size
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

def initialize_symbols(symbol_array):
    """Enable symbols in MetaTrader 5."""
    logging.info("Initializing symbols...")
    for symbol in symbol_array:
        if mt5.symbol_select(symbol, True):
            logging.info(f"Symbol {symbol} initialized.")
        else:
            logging.error(f"Failed to initialize symbol: {symbol}")
            return False
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
    gain = delta.where(delta > 0, 0).rolling(window=RSI_PERIOD).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # Calculate EMAs
    data['EMA_50'] = data['close'].ewm(span=EMA_SHORT).mean()
    data['EMA_200'] = data['close'].ewm(span=EMA_LONG).mean()

    return data

def place_trade_with_programmatic_tp(symbol, order_type):
    """Place a trade with programmatic take-profit management."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logging.error(f"Failed to get market tick for {symbol}.")
        return
    
    price = tick.ask if order_type.lower() == "buy" else tick.bid
    point = mt5.symbol_info(symbol).point

    tp_levels = [
        price + (120 * point) if order_type.lower() == "buy" else price - (120 * point),
        price + (240 * point) if order_type.lower() == "buy" else price - (240 * point),
        price + (360 * point) if order_type.lower() == "buy" else price - (360 * point),
    ]
    
    logging.info(f"Placing {order_type.upper()} order for {symbol} at price {price}.")
    try:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": mt5.ORDER_TYPE_BUY if order_type.lower() == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": DEVIATION,
            "magic": MAGIC_NUMBER,
            "comment": "Programmatic TP",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order placement failed: {result.retcode}")
            return
        else:
            logging.info(f"Order placed successfully. Ticket: {result.order}")

    except Exception as e:
        logging.error(f"Error placing trade: {e}")

def main():
    for symbol in SYMBOLS:
        logging.info(f"Processing {symbol}")
        
        data = fetch_data(symbol)
        if data is not None:
            rsi = data['RSI'].iloc[-1]
            ema_50 = data['EMA_50'].iloc[-1]
            ema_200 = data['EMA_200'].iloc[-1]

            if rsi < 30 and ema_50 > ema_200:
                logging.info(f"{symbol} BUY condition met: RSI={rsi}, EMA_50={ema_50}, EMA_200={ema_200}")
                place_trade_with_programmatic_tp(symbol, "buy")
                
            elif rsi > 70 and ema_50 < ema_200:
                logging.info(f"{symbol} SELL condition met: RSI={rsi}, EMA_50={ema_50}, EMA_200={ema_200}")
                place_trade_with_programmatic_tp(symbol, "sell")
        else:
            logging.error(f"Failed to fetch data for {symbol}")

schedule.every(1).minutes.do(main)

if initialize_mt5(settings):
    if initialize_symbols(SYMBOLS):
        while True:
            schedule.run_pending()
            time.sleep(1)
else:
    logging.error("MT5 initialization failed. Exiting script.")
