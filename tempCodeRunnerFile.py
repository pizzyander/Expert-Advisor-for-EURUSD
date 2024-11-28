import MetaTrader5 as mt5
import pandas as pd
import logging
import time
from datetime import datetime
from finta import TA  # Import finta's TA module

# Account details
account_details = {
    "login": 9293182,
    "password": "Ge@mK3Xb",
    "server": "GTCGlobalTrade-Server",
    "mt5_pathway": "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
}

# Symbols to trade
symbols = ["EURUSD", "XAUUSD", "USDJPY", "GBPUSD"]

# Trade parameters
volume = 0.1  # Fixed trade volume
h4_timeframe = mt5.TIMEFRAME_H4
h1_timeframe = mt5.TIMEFRAME_H1
tp1_pips = 120
tp2_pips = 240
tp3_pips = 360

# Logging configuration
logging.basicConfig(
    filename="trading_bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("Starting the trading bot script.")

# Initialize MetaTrader 5
if not mt5.initialize(account_details["mt5_pathway"]):
    logging.error("Failed to initialize MetaTrader 5. Exiting.")
    quit()

# Login to MT5 account
if not mt5.login(account_details["login"], account_details["password"], account_details["server"]):
    logging.error("Failed to log in to MT5 account. Exiting.")
    mt5.shutdown()
    quit()
logging.info(f"Logged in to MT5 account: {account_details['login']}.")

# Main function to execute trades for each symbol
def run_trading_bot():
    try:
        for symbol in symbols:
            logging.info(f"Processing symbol: {symbol}.")

            # Check if symbol is available in the terminal
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logging.warning(f"Symbol {symbol} not found. Skipping.")
                continue
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    logging.warning(f"Symbol {symbol} is not visible and could not be enabled. Skipping.")
                    continue

            # Fetch H4 data for trend detection
            h4_rates = mt5.copy_rates_from_pos(symbol, h4_timeframe, 0, 500)
            h4_df = pd.DataFrame(h4_rates)
            h4_df['time'] = pd.to_datetime(h4_df['time'], unit='s')

            # Calculate ADX to detect trend direction using finta
            adx = TA.ADX(h4_df)  # finta ADX
            if adx.iloc[-1]['ADX'] <= 25:  # Weak trend
                logging.info(f"No strong trend detected for {symbol}. Skipping this cycle.")
                continue
            trend_direction = "uptrend" if h4_df['close'].iloc[-1] > h4_df['open'].iloc[-1] else "downtrend"
            logging.info(f"Trend detected for {symbol}: {trend_direction}.")

            # Detect swing highs and swing lows
            h4_df['swing_high'] = (h4_df['high'] > h4_df['high'].shift(1)) & (h4_df['high'] > h4_df['high'].shift(-1))
            h4_df['swing_low'] = (h4_df['low'] < h4_df['low'].shift(1)) & (h4_df['low'] < h4_df['low'].shift(-1))

            # Fetch H1 data for break of structure confirmation
            h1_rates = mt5.copy_rates_from_pos(symbol, h1_timeframe, 0, 500)
            h1_df = pd.DataFrame(h1_rates)
            h1_df['time'] = pd.to_datetime(h1_df['time'], unit='s')

            # Break of structure confirmation
            bos_confirmed = False
            if trend_direction == "uptrend":
                resistance = h4_df[h4_df['swing_high']]['high'].max()
                if h1_df['close'].iloc[-1] > resistance:
                    bos_confirmed = True
                    logging.info(f"Break of structure confirmed for {symbol} in uptrend.")
            elif trend_direction == "downtrend":
                support = h4_df[h4_df['swing_low']]['low'].min()
                if h1_df['close'].iloc[-1] < support:
                    bos_confirmed = True
                    logging.info(f"Break of structure confirmed for {symbol} in downtrend.")

            if not bos_confirmed:
                logging.info(f"No break of structure confirmed for {symbol}. Skipping this cycle.")
                continue

            # Place a single trade with partial TP levels
            entry_price = h1_df['close'].iloc[-1]
            tp1 = entry_price + (tp1_pips * symbol_info.point) if trend_direction == "uptrend" else entry_price - (tp1_pips * symbol_info.point)
            tp2 = entry_price + (tp2_pips * symbol_info.point) if trend_direction == "uptrend" else entry_price - (tp2_pips * symbol_info.point)
            tp3 = entry_price + (tp3_pips * symbol_info.point) if trend_direction == "uptrend" else entry_price - (tp3_pips * symbol_info.point)

            # Place the trade
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_BUY if trend_direction == "uptrend" else mt5.ORDER_SELL,
                "price": entry_price,
                "tp": tp1,
                "deviation": 10,
                "magic": 123456,
                "comment": "Partial TP Trade",
            }

            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logging.info(f"Trade placed for {symbol}: {result}")
            else:
                logging.error(f"Failed to place trade for {symbol}. Error: {result.comment}")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")


# Run the bot every 10 minutes
while True:
    logging.info(f"Running bot cycle at {datetime.now()}.")
    run_trading_bot()
    logging.info("Sleeping for 10 minutes before the next cycle.")
    time.sleep(10 * 60)
