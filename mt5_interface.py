import MetaTrader5 as MetaTrader5
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from main import app

# Set up logging
logging.basicConfig(level=logging.INFO, filename="bot.log", filemode="a", 
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize MT5
def start_mt5(username, password, server, path):
    if MetaTrader5.initialize(login=int(username), password=password, server=server, path=path):
        logging.info("MT5 Initialized Successfully.")
        if MetaTrader5.login(login=int(username), password=password, server=server):
            logging.info("Logged in to MT5.")
            return True
        else:
            logging.error(f"Login Failed: {MetaTrader5.last_error()}")
            MetaTrader5.shutdown()
            return False
    else:
        logging.error(f"MT5 Initialization Failed: {MetaTrader5.last_error()}")
        return False

# Initialize symbols
def initialize_symbols(symbol_array):
    all_symbols = [symbol.name for symbol in MetaTrader5.symbols_get()]
    for provided_symbol in symbol_array:
        if provided_symbol not in all_symbols:
            raise Exception(f"Symbol '{provided_symbol}' is not available in MT5.")
        elif not MetaTrader5.symbol_select(provided_symbol, True):
            raise Exception(f"Failed to enable symbol '{provided_symbol}'.")
    logging.info("All symbols initialized successfully.")

# Retrieve last 90 H1 candles
def get_last_90_candles(symbol):
    rates = MetaTrader5.copy_rates_from_pos(symbol, MetaTrader5.TIMEFRAME_H1, 0, 90)
    if not rates:
        logging.error(f"Failed to retrieve candlestick data for {symbol}.")
        return None
    return [{"open": r.open, "high": r.high, "low": r.low, "close": r.close} for r in rates]

# Get prediction from FastAPI
def get_prediction(candle_data):
    url = "http://127.0.0.1:8000/predict"  # Update if necessary
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retry))

    try:
        response = session.post(url, json={"features": candle_data})
        response.raise_for_status()
        return response.json().get("prediction")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error with FastAPI request: {e}")
        return None

# Place trade
def place_trade(symbol, order_type):
    lot_size = 0.1
    tick = MetaTrader5.symbol_info_tick(symbol)
    pip = 0.0001 if "JPY" not in symbol else 0.01
    price = tick.ask if order_type == "buy" else tick.bid
    sl = price - (30 * pip) if order_type == "buy" else price + (30 * pip)
    tp = price + (60 * pip) if order_type == "buy" else price - (60 * pip)

    request = {
        "action": MetaTrader5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": MetaTrader5.ORDER_TYPE_BUY if order_type == "buy" else MetaTrader5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "comment": f"Prediction {order_type.capitalize()}",
        "type_time": MetaTrader5.ORDER_TIME_GTC,
        "type_filling": MetaTrader5.ORDER_FILLING_RETURN,
    }

    result = MetaTrader5.order_send(request)
    if result.retcode != MetaTrader5.TRADE_RETCODE_DONE:
        logging.error(f"Error placing order: {result.retcode}")
    else:
        logging.info(f"Order placed successfully. Ticket: {result.order}")
