import MetaTrader5 as mt5
import time
import pandas as pd
from trading import Trading

def main_process(symbol, timeframe, lot_size=10000, polling_interval=60):
    trading = Trading(symbol)
    # MT5に接続
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()

    # ポートフォリオを初期化
    portfolio = {'position': None, 'entry_price': None}

    try:
        while True:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 200)  # 直近200データを取得
            if rates is None:
                print("Error in copy_rates_from_pos(), error code =", mt5.last_error())
                continue
        
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = trading.prepare_data(df)

            position = trading.get_position()
            signal = trading.trade_conditions(df, len(df)-1, portfolio)

            # order parameters
            order_type = mt5.ORDER_TYPE_BUY
            volume = 1.0
            point = mt5.symbol_info(symbol).point
            price = mt5.symbol_info_tick(symbol).ask
            stop_loss = price - 100 * point
            take_profit = price + 100 * point

            if signal == 'entry_long' and position is None:
                order_type = mt5.ORDER_TYPE_BUY
                trading.place_order(symbol, order_type, volume, price, stop_loss, take_profit)
                portfolio['position'] = 'long'
                portfolio['entry_price'] = df.loc[len(df)-1, 'close']
            elif signal == 'exit_long' and portfolio['position'] == 'long':
                order_type = mt5.ORDER_TYPE_SELL
                trading.close_position(position["id"])
                portfolio['position'] = None
                portfolio['entry_price'] = None

            time.sleep(polling_interval)

    except Exception as e:
        print("An error occurred:", str(e))
    finally:
        # MT5との接続を閉じる
        mt5.shutdown()


main_process('USDJPY', mt5.TIMEFRAME_M5)
