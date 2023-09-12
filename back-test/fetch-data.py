import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import pytz
import os

try:
    # MT5に接続
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()

    # タイムゾーンをUTCに設定する
    symbol = "USDSEK"
    timeframe = mt5.TIMEFRAME_M1
    timezone = pytz.timezone("Etc/UTC")
    utc_from = datetime(2022, 8, 1, tzinfo=timezone)
    utc_to = datetime(2023, 8, 1, hour = 13, tzinfo=timezone)
    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)

    if rates is None:
        raise Exception("No data received, error code =", mt5.last_error())

    if len(rates) == 1:
        rates = [rates[0]]

    # DataFrameに変換
    df = pd.DataFrame(rates,
        columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])

    # タイムスタンプを変換
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # CSVファイルとして保存
    csv_folder = 'csv'
    if not os.path.exists(csv_folder):
        os.makedirs(csv_folder)

    from_date_str = utc_from.strftime("%Y%m%d")
    to_date_str = utc_to.strftime("%Y%m%d")
    csv_file = os.path.join(csv_folder, f'{symbol}_{timeframe}_{from_date_str}_to_{to_date_str}.csv')
    df.to_csv(csv_file, index=False)

    print(f"{csv_file} has been saved.")

except Exception as e:
    print("An error occurred:", str(e))

finally:
    # MT5との接続を閉じる
    mt5.shutdown()
