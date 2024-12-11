import MetaTrader5 as mt5
import pandas as pd
import logging
import time
from datetime import datetime

# Logging configuration
log_file = "strategy1.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Add console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)

# Constants
RSI_PERIOD = 14
EMA_SHORT = 50
EMA_LONG = 200
RISK_PERCENT = 0.02
MAGIC_NUMBER = 456000
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
PIP_VALUES = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.01}

MT5_PATH = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
USERNAME = 9293182
PASSWORD = "Ge@mK3Xb"
SERVER = "GTCGlobalTrade-Server"


def initialize_mt5(settings):
    """Initialize MetaTrader 5 connection."""
    logging.info("Initializing MT5...")
    if not mt5.initialize(path=settings["mt5Pathway"]):
        logging.error(f"MT5 initialization failed: {mt5.last_error()}")
        return False

    if not mt5.login(settings["username"], settings["password"], settings["server"]):
        logging.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False

    logging.info("MT5 initialized and logged in successfully.")
    return True


def fetch_data(symbol, timeframe=mt5.TIMEFRAME_H1):
    """Fetch historical data and calculate indicators."""
    logging.info(f"Fetching data for symbol: {symbol}")
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


def place_trade(trade_type, symbol, entry_price):
    """Place a single trade with specified parameters."""
    logging.info(f"Placing {trade_type} trade for {symbol} at entry price {entry_price}")

    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if trade_type == "BUY" else tick.bid
    if price is None:
        logging.error(f"Failed to retrieve price for {symbol}.")
        return None

    lot_size = 0.1
    point = mt5.symbol_info(symbol).point
    tp_levels = [
        price + (120 * point) if trade_type == "BUY" else price - (120 * point),
        price + (240 * point) if trade_type == "BUY" else price - (240 * point),
        price + (360 * point) if trade_type == "BUY" else price - (360 * point),
    ]
    tp_lot_sizes = [0.1, 0.1, 0.1]

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if trade_type == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": "Programmatic TP",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order placement failed: {result.retcode}")
        return

    logging.info(f"Order placed successfully. Ticket: {result.order}")
    ticket = result.order

    for i, tp in enumerate(tp_levels):
        while True:
            current_price = (
                mt5.symbol_info_tick(symbol).bid if trade_type == "BUY" else mt5.symbol_info_tick(symbol).ask
            )
            if (trade_type == "BUY" and current_price >= tp) or (
                trade_type == "SELL" and current_price <= tp
            ):
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": tp_lot_sizes[i],
                    "type": mt5.ORDER_TYPE_SELL if trade_type == "BUY" else mt5.ORDER_TYPE_BUY,
                    "position": ticket,
                    "price": current_price,
                    "deviation": 10,
                    "magic": MAGIC_NUMBER,
                    "comment": f"TP Level {i+1} closure",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                close_result = mt5.order_send(close_request)

                if close_result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Failed to close at TP Level {i+1}: {close_result.retcode}")
                else:
                    logging.info(f"Successfully closed {tp_lot_sizes[i]} lots at TP Level {i+1}.")
                break

            time.sleep(1)


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

    if ema_50 > ema_200 and rsi < 25:
        place_trade("BUY", symbol, current_price)
    elif ema_50 < ema_200 and rsi > 75:
        place_trade("SELL", symbol, current_price)

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
            logging.info("Cycle complete. Sleeping for 2 hours.")
            time.sleep(3600 * 6)
    finally:
        mt5.shutdown()


def main():
    """Main function to set up and execute the trading strategy."""
    mt5_settings = {
        "mt5Pathway": MT5_PATH,
        "username": USERNAME,
        "password": PASSWORD,
        "server": SERVER,
    }

    logging.info("Starting the trading bot.")
    try:
        execute_strategy(mt5_settings)
    except KeyboardInterrupt:
        logging.info("Trading bot interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected error occurred: {str(e)}")
    finally:
        logging.info("Trading bot stopped.")

if __name__ == "__main__":
    main()