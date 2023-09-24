import MetaTrader5 as mt5
import configparser
import time
import pandas as pd
import traceback
from trading import Trading

def main_process(polling_interval=60):

    settings_reversal_usdjpy = { 
        'symbol': 'USDJPY',
        'risk_reward_ratio': 1.2, # 1.0
        'stop_loss_pips': 0.10, # 0.10
        'base_spread_pips': 0.03, # 0.03
        'df_sliced_period': 500, # 300~500
        'distance': 7, # 5~7
    }

    params = settings_reversal_usdjpy
    trading = Trading(params=params)

    # MT5に接続
    config = configparser.ConfigParser()
    config.read('settings.ini')
    provider = 'OANDA'

    mt5_path = config[provider]['mt5_path']
    mt5_login = int(config[provider]['mt5_login'])
    mt5_password = config[provider]['mt5_password']
    mt5_server = config[provider]['mt5_server']

    print("===== MT5 Connection Settings =====")
    print(f"- MT5 Path: {mt5_path}")
    print(f"- MT5 Login: {mt5_login}") 
    print(f"- MT5 Password: {'*' * len(mt5_password)}")  
    print(f"- MT5 Server: {mt5_server}")
    print("===================================")

    if not mt5.initialize(path=mt5_path, login=mt5_login, password=mt5_password, server=mt5_server):
        print("initialize() failed, error code =", mt5.last_error())
        quit()

    # ポートフォリオを初期化
    portfolio = {'position': None, 'entry_price': None}

    try:
        while True:
            bar_count = 500 # 直近N本のデータを取得
            rates = mt5.copy_rates_from_pos(params['symbol'], mt5.TIMEFRAME_M1, 0, bar_count)
            if rates is None:
                print("Error in copy_rates_from_pos(), error code =", mt5.last_error())
                continue

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')

            position = trading.get_position()

            lot = 0.01 # 1ロット=100,000通貨　(最小取引数量 10,000通貨)
            signal = trading.trade_conditions(df, len(df)-1, portfolio)
            print(f'signal: {signal}')

            # order parameters
            order_type = mt5.ORDER_TYPE_BUY
            point = mt5.symbol_info(params['symbol']).point
            price = mt5.symbol_info_tick(params['symbol']).ask
            stop_loss = price - 100 * point
            take_profit = price + 100 * point

            if signal == 'entry_long' and position is None:
                order_type = mt5.ORDER_TYPE_BUY
                trading.place_order(params['symbol'], order_type, lot, price, stop_loss, take_profit)
                portfolio['position'] = 'long'
            elif signal == 'exit_long' and portfolio['position'] == 'long':
                order_type = mt5.ORDER_TYPE_SELL
                trading.close_position(position["id"])
                portfolio['position'] = None
                portfolio['entry_price'] = None

            time.sleep(polling_interval)

    except Exception as e:
        print("An error occurred:", str(e))
        traceback.print_exc()
    finally:
        # MT5との接続を閉じる
        mt5.shutdown()


main_process()
