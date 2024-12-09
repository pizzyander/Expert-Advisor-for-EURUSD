import MetaTrader5 as mt5
import pandas as pd
import logging
import time
from datetime import datetime
from finta import TA
from concurrent.futures import ThreadPoolExecutor

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
risk_percent = 1.0  # Risk percentage per trade
h4_timeframe = mt5.TIMEFRAME_H4
h1_timeframe = mt5.TIMEFRAME_H1
adx_threshold = 20  # Lowered for more trade opportunities
rsi_overbought = 70
rsi_oversold = 30
sl_pips = 50  # Tighter stop-loss for more frequent trades

# Logging configuration
logging.basicConfig(
    filename="trading_bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

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


def fetch_data(symbol, timeframe, num_candles=200):
    """Fetch historical data for the specified symbol and timeframe."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
    if rates is None or len(rates) == 0:
        logging.error(f"Failed to fetch data for {symbol}.")
        return None
    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s')
    return data


def calculate_lot_size(risk_percent, balance, symbol):
    """Calculate the lot size based on risk percentage and account balance."""
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        logging.error(f"Failed to get symbol info for {symbol}.")
        return 0.01
    point = symbol_info.point
    tick_value = symbol_info.trade_tick_value
    lot_size = (balance * risk_percent / 100) / (sl_pips * point * tick_value)
    return max(round(lot_size, 2), symbol_info.volume_min)


def analyze_and_trade(symbol):
    """Analyze market conditions and execute trades."""
    try:
        logging.info(f"Analyzing symbol: {symbol}")

        # Fetch H4 data for trend and H1 for confirmation
        h4_data = fetch_data(symbol, h4_timeframe, num_candles=100)
        h1_data = fetch_data(symbol, h1_timeframe, num_candles=50)

        if h4_data is None or h1_data is None:
            logging.warning(f"Skipping {symbol} due to data issues.")
            return

        # Detect trend using ADX
        adx = TA.ADX(h4_data)
        trend = None
        if adx.iloc[-1]['ADX'] > adx_threshold:
            trend = "uptrend" if h4_data['close'].iloc[-1] > h4_data['close'].iloc[-2] else "downtrend"

        # Check RSI divergence
        rsi = TA.RSI(h1_data)
        if trend == "uptrend" and rsi.iloc[-1]['RSI'] > rsi_overbought:
            logging.info(f"RSI divergence confirmed for {symbol} in uptrend.")
        elif trend == "downtrend" and rsi.iloc[-1]['RSI'] < rsi_oversold:
            logging.info(f"RSI divergence confirmed for {symbol} in downtrend.")
        else:
            logging.info(f"No RSI divergence for {symbol}. Skipping.")
            return

        # Fetch account balance
        account_info = mt5.account_info()
        if not account_info:
            logging.error("Failed to fetch account info.")
            return
        lot_size = calculate_lot_size(risk_percent, account_info.balance, symbol)

        # Define trade parameters
        entry_price = h1_data['close'].iloc[-1]
        sl = entry_price - (sl_pips * mt5.symbol_info(symbol).point) if trend == "uptrend" else entry_price + (
                    sl_pips * mt5.symbol_info(symbol).point)
        tp = entry_price + (2 * sl_pips * mt5.symbol_info(symbol).point) if trend == "uptrend" else entry_price - (
                    2 * sl_pips * mt5.symbol_info(symbol).point)

        # Place trade
        order_type = mt5.ORDER_BUY if trend == "uptrend" else mt5.ORDER_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": entry_price,
            "sl": sl,
            "tp": tp,
            "deviation": 100,
            "magic": 123000,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"Trade placed for {symbol}. Order ID: {result.order}")
        else:
            logging.error(f"Failed to place trade for {symbol}. Error: {result.comment}")

    except Exception as e:
        logging.error(f"Error in analyzing and trading {symbol}: {str(e)}")


def main():
    logging.info("Starting trading bot.")
    with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
        while True:
            executor.map(analyze_and_trade, symbols)
            logging.info("Cycle complete. Sleeping for 30 minutes.")
            time.sleep(30 * 60)


if __name__ == "__main__":
    main()
