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
    """
    Place a trade with take-profit levels at 120, 240, and 360 pips above or below the entry price.
    """
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logging.error(f"Failed to get market tick for {symbol}.")
        return
    
    # Determine entry price and point value
    price = tick.ask if order_type.lower() == "buy" else tick.bid
    point = mt5.symbol_info(symbol).point  # Point value for the symbol

    # Calculate take-profit levels
    tp_120 = price + (120 * point) if order_type.lower() == "buy" else price - (120 * point)
    tp_240 = price + (240 * point) if order_type.lower() == "buy" else price - (240 * point)
    tp_360 = price + (360 * point) if order_type.lower() == "buy" else price - (360 * point)
    
    logging.info(
        f"Placing {order_type.upper()} order for {symbol} at price {price} with TPs: "
        f"120 pips ({tp_120}), 240 pips ({tp_240}), 360 pips ({tp_360})."
    )

    try:
        # Place the trade
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": mt5.ORDER_TYPE_BUY if order_type.lower() == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": None,  # Stop loss can be added here if needed
            "tp": tp_120,  # Initial TP at 120 pips
            "deviation": DEVIATION,
            "magic": MAGIC_NUMBER,
            "comment": "Take-Profit Strategy",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order placement failed: {result.retcode}")
            return
        else:
            logging.info(f"Order placed successfully. Ticket: {result.order}")

            # Manage take-profits dynamically
            ticket = result.order
            for tp_level, tp_desc in zip([tp_240, tp_360], ["240 pips", "360 pips"]):
                logging.info(f"Waiting for {tp_desc} level.")
                while True:
                    current_price = tick.ask if order_type.lower() == "buy" else tick.bid

                    if (order_type.lower() == "buy" and current_price >= tp_level) or (
                        order_type.lower() == "sell" and current_price <= tp_level
                    ):
                        logging.info(f"Reached {tp_desc} for {symbol}. Closing partial position.")
                        
                        close_request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": symbol,
                            "volume": LOT_SIZE,  # Adjust volume for partial closure
                            "type": mt5.ORDER_TYPE_SELL if order_type.lower() == "buy" else mt5.ORDER_TYPE_BUY,
                            "position": ticket,
                            "price": current_price,
                            "deviation": DEVIATION,
                            "magic": MAGIC_NUMBER,
                            "comment": f"Close at {tp_desc}",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }

                        close_result = mt5.order_send(close_request)
                        if close_result.retcode != mt5.TRADE_RETCODE_DONE:
                            logging.error(f"Failed to close at {tp_desc}: {close_result.retcode}")
                        else:
                            logging.info(f"Closed partial position at {tp_desc}.")
                        break  # Exit loop and proceed to the next TP level
                    time.sleep(1)  # Check the price every second

    except Exception as e:
        logging.error(f"Error placing trade or managing TPs: {e}")

def get_market_trend(symbol, timeframe=mt5.TIMEFRAME_H1):
    """
    Analyze the market trend for a given symbol.
    Determine if the market is trending or consolidating.
    """
    logging.info(f"Analyzing market trend for {symbol}...")
    
    # Fetch the last 300 H1 candlesticks
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 300)
    if rates is None or len(rates) == 0:
        logging.error(f"Failed to fetch data for market trend analysis: {symbol}.")
        return None

    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s')

    # Calculate ATR
    data['high_low'] = data['high'] - data['low']
    data['high_close'] = abs(data['high'] - data['close'].shift(1))
    data['low_close'] = abs(data['low'] - data['close'].shift(1))
    data['TR'] = data[['high_low', 'high_close', 'low_close']].max(axis=1)
    data['ATR'] = data['TR'].rolling(window=14).mean()

    # Calculate EMA (200)
    data['EMA_200'] = data['close'].ewm(span=200).mean()

    # Determine the trend direction using EMA slope
    ema_diff = data['EMA_200'].diff()
    average_ema_slope = ema_diff[-10:].mean()  # Average slope over the last 10 periods

    # Determine if ATR indicates consolidation
    avg_atr = data['ATR'][-20:].mean()  # Average ATR over the last 20 periods
    consolidation_threshold = 0.001 * mt5.symbol_info(symbol).point

    if abs(average_ema_slope) < consolidation_threshold and avg_atr < consolidation_threshold:
        trend = "consolidating"
    elif average_ema_slope > 0:
        trend = "uptrend"
    elif average_ema_slope < 0:
        trend = "downtrend"
    else:
        trend = "indeterminate"

    logging.info(f"{symbol} market trend: {trend} (ATR={avg_atr:.6f}, EMA slope={average_ema_slope:.6f})")
    return trend

def main():
    for symbol in SYMBOLS:
        logging.info(f"Processing {symbol}")

        # Determine market trend
        trend = get_market_trend(symbol)
        if trend == "consolidating":
            logging.info(f"Skipping trades for {symbol} due to consolidation.")
            continue

        # Fetch the market data for the symbol
        data = fetch_data(symbol)
        if data is not None:
            rsi = data['RSI'].iloc[-1]
            ema_50 = data['EMA_50'].iloc[-1]
            ema_200 = data['EMA_200'].iloc[-1]

            # Example strategy: Buy in uptrend when RSI < 30 and EMA50 > EMA200
            if trend == "uptrend" and rsi < 30 and ema_50 > ema_200:
                logging.info(f"{symbol} BUY condition met: RSI={rsi}, EMA_50={ema_50}, EMA_200={ema_200}")
                place_trade_with_programmatic_tp(symbol, "buy")

            # Example strategy: Sell in downtrend when RSI > 70 and EMA50 < EMA200
            elif trend == "downtrend" and rsi > 70 and ema_50 < ema_200:
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
