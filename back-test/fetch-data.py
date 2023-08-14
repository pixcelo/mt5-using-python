import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import pytz

try:
    # MT5に接続
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()

    # 通貨ペアと時間枠を指定
    symbol = "USDJPY"
    timeframe = mt5.TIMEFRAME_M1

    # タイムゾーンをUTCに設定する
    # utc_from = datetime(2023, 1, 1, tzinfo=timezone.utc)
    # utc_to = datetime(2020, 5, 1, 23, 59, tzinfo=timezone.utc)
    # rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)  

    # タイムゾーンをUTCに設定する
    timezone = pytz.timezone("Etc/UTC")
    # create 'datetime' objects in UTC time zone to avoid the implementation of a local time zone offset
    utc_from = datetime(2023, 1, 10, tzinfo=timezone)
    utc_to = datetime(2023, 8, 1, hour = 13, tzinfo=timezone)
    # 2020.01.10 00:00-2020.01.11 13:00 UTCでUSDJPY M5からバーを取得する
    rates = mt5.copy_rates_range("USDJPY", mt5.TIMEFRAME_M5, utc_from, utc_to)

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
    csv_file = f'{symbol}_{timeframe}.csv'
    df.to_csv(csv_file, index=False)

    print(f"{csv_file} has been saved.")

except Exception as e:
    print("An error occurred:", str(e))

finally:
    # MT5との接続を閉じる
    mt5.shutdown()
