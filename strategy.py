import MetaTrader5 as mt5
import pandas as pd
import logging
from datetime import datetime, timedelta
import time

# Set up logging
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
REWARD_RATIOS = [1, 2, 3]  # Multiples for calculating take profits, not needed now
MAGIC_NUMBER = 456000
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]  # Add more symbols as needed

def initialize_mt5(settings):
    """Initialize MetaTrader 5 connection with provided settings."""
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


def fetch_data(symbol, timeframe=mt5.TIMEFRAME_H4):
    """Fetch historical data for a symbol and calculate technical indicators."""
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


def calculate_lot_size(risk_percent, sl_distance):
    """Calculate the lot size based on the account balance and stop-loss distance."""
    account_info = mt5.account_info()
    if account_info is None:
        logging.error("Failed to fetch account information.")
        return 0

    balance = account_info.balance
    risk_amount = balance * risk_percent
    lot_size = risk_amount / (sl_distance / 0.0001)
    return round(lot_size, 2)


def place_trade(trade_type, symbol, lot_size, entry_price, take_profits):
    """Place a trade with the specified parameters using instant execution."""
    price = mt5.symbol_info_tick(symbol).ask if trade_type == "BUY" else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,  # Instant market execution
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if trade_type == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,  # Use the current price for market execution
        "sl": None,  # No stop-loss is used in this setup
        "tp": take_profits[0],  # First take profit level as requested
        "deviation": 20,
        "magic": MAGIC_NUMBER,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Failed to place {trade_type} trade for {symbol}: {result.comment}")
    else:
        logging.info(f"Successfully placed {trade_type} trade for {symbol}. TP levels: {take_profits}")


def analyze_and_trade(symbol):
    """Analyze market conditions (RSI, EMA) and execute trades accordingly."""
    data = fetch_data(symbol)
    if data is None:
        return

    current_price = data['close'].iloc[-1]
    ema_50 = data['EMA_50'].iloc[-1]
    ema_200 = data['EMA_200'].iloc[-1]
    rsi = data['RSI'].iloc[-1]

    # Calculate take-profit levels (120, 240, 360 pips away)
    tp_120 = current_price + 120 * 0.0001
    tp_240 = current_price + 240 * 0.0001
    tp_360 = current_price + 360 * 0.0001
    take_profits = [tp_120, tp_240, tp_360]

    # Trend-following logic
    if ema_50 > ema_200 and rsi < 40:  # Buy condition
        lot_size = calculate_lot_size(RISK_PERCENT, 120)  # 120 pips used for lot size calculation
        place_trade("BUY", symbol, lot_size, current_price, take_profits)

    elif ema_200 > ema_50 and rsi > 60:  # Sell condition
        lot_size = calculate_lot_size(RISK_PERCENT, 120)  # 120 pips used for lot size calculation
        take_profits = [tp_120, tp_240, tp_360]  # Reapply take profit levels for sell
        place_trade("SELL", symbol, lot_size, current_price, take_profits)

    logging.info(f"Trade analyzed for {symbol}: EMA_50={ema_50}, EMA_200={ema_200}, RSI={rsi}.")


# Main loop to execute the strategy every 2 minutes for each symbol
def main():
    """Main function to loop through symbols and execute the strategy."""
    while True:
        logging.info("Starting strategy execution cycle.")
        for symbol in SYMBOLS:
            analyze_and_trade(symbol)
        logging.info("Cycle complete. Sleeping for 2 minutes.")
        time.sleep(2 * 60)


if __name__ == "__main__":
    mt5_settings = {
        "username": 9293182,
        "password": "Ge@mK3Xb",
        "server": "GTCGlobalTrade-Server",
        "mt5Pathway": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    }
    if initialize_mt5(mt5_settings):
        main()
    else:
        logging.error("Failed to initialize MT5. Exiting.")
