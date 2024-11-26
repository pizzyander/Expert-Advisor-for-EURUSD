import MetaTrader5 as mt5
import pandas as pd
import talib
import logging
import time
from datetime import datetime

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
lot_size = 1.0
h4_timeframe = mt5.TIMEFRAME_H4
h1_timeframe = mt5.TIMEFRAME_H1
sl_pips = 80  # Stop Loss in pips
tp1_ratio = 1  # TP1 = SL x 1
tp2_ratio = 2  # TP2 = SL x 2
tp3_ratio = 3  # TP3 = SL x 3

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
            logging.info(f"Fetching H4 data for {symbol}.")
            h4_rates = mt5.copy_rates_from_pos(symbol, h4_timeframe, 0, 500)
            h4_df = pd.DataFrame(h4_rates)
            h4_df['time'] = pd.to_datetime(h4_df['time'], unit='s')

            # Calculate ADX to detect trend direction
            adx = talib.ADX(h4_df['high'], h4_df['low'], h4_df['close'], timeperiod=14)
            trend_direction = None
            if adx.iloc[-1] > 25:
                trend_direction = "uptrend" if h4_df['close'].iloc[-1] > h4_df['close'].iloc[-2] else "downtrend"
                logging.info(f"Trend detected for {symbol}: {trend_direction}.")
            else:
                logging.info(f"No strong trend detected for {symbol}. Skipping this cycle.")
                continue

            # Detect swing highs and swing lows
            h4_df['swing_high'] = (h4_df['high'] > h4_df['high'].shift(1)) & (h4_df['high'] > h4_df['high'].shift(-1))
            h4_df['swing_low'] = (h4_df['low'] < h4_df['low'].shift(1)) & (h4_df['low'] < h4_df['low'].shift(-1))

            # Fetch H1 data for break of structure confirmation
            logging.info(f"Fetching H1 data for {symbol}.")
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

            # RSI divergence confirmation
            logging.info(f"Checking RSI divergence for {symbol}.")
            rsi = talib.RSI(h1_df['close'], timeperiod=14)
            if (trend_direction == "uptrend" and rsi.iloc[-1] < 40) or (trend_direction == "downtrend" and rsi.iloc[-1] > 60):
                logging.info(f"RSI divergence not confirmed for {symbol}. Skipping this cycle.")
                continue

            # Calculate entry, SL, and TP levels
            logging.info(f"Calculating entry, SL, and TP levels for {symbol}.")
            entry_price = h1_df['close'].iloc[-1]
            sl = entry_price - (sl_pips * mt5.symbol_info(symbol).point) if trend_direction == "uptrend" else entry_price + (sl_pips * mt5.symbol_info(symbol).point)
            tp1 = entry_price + (sl_pips * tp1_ratio * mt5.symbol_info(symbol).point) if trend_direction == "uptrend" else entry_price - (sl_pips * tp1_ratio * mt5.symbol_info(symbol).point)
            tp2 = entry_price + (sl_pips * tp2_ratio * mt5.symbol_info(symbol).point) if trend_direction == "uptrend" else entry_price - (sl_pips * tp2_ratio * mt5.symbol_info(symbol).point)
            tp3 = entry_price + (sl_pips * tp3_ratio * mt5.symbol_info(symbol).point) if trend_direction == "uptrend" else entry_price - (sl_pips * tp3_ratio * mt5.symbol_info(symbol).point)

            # Place orders
            logging.info(f"Placing orders for {symbol}.")
            order_tp1 = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size / 3,
                "type": mt5.ORDER_BUY if trend_direction == "uptrend" else mt5.ORDER_SELL,
                "price": entry_price,
                "sl": sl,
                "tp": tp1,
                "deviation": 10,
                "magic": 123456,
                "comment": "TP1",
            }

            # Send orders
            result_tp1 = mt5.order_send(order_tp1)
            if result_tp1.retcode == mt5.TRADE_RETCODE_DONE:
                logging.info(f"Order for {symbol} placed successfully: TP1.")
            else:
                logging.error(f"Failed to place order for {symbol}. Error: {result_tp1.comment}")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")


# Run the bot every 30 minutes
while True:
    logging.info(f"Running bot cycle at {datetime.now()}.")
    run_trading_bot()
    logging.info("Sleeping for 30 minutes before the next cycle.")
    time.sleep(30 * 60)
