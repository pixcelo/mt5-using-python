import pandas as pd
from scipy.signal import find_peaks
import numpy as np
from datetime import datetime
import logging

class TradingStrategy:
    """
    トレードロジック
    使用データ: 1分足と5分足データを取得（1分足から5分足をリサンプリング）
    1. ５分足のチャート参照
        連続する安値が上昇しているポイントを特定。（極大値・極小値のピーク）
    2. トレンドライン(1)の作成
        上昇する安値のポイントを結ぶ直線を描きます。
        この直線を「トレンドライン(1)」と呼びます。
        ※トレンドラインの定義：（下降トレンドなら極大値の切り下がり、上昇トレンドなら極小値のピークの切り上がり）を結んだもの
        トレンドラインの延長線上に、将来クロスするポイントを見つける
    3. 最新の高値の特定
        ５分足のチャートでの最新の高値を特定します。
    4. 水平線(2)の作成
        最新の高値から水平に直線を引きます。
        この直線を「水平線(2)」と呼びます。
    5. 三角形の形状の作成
        「トレンドライン(1)」と「水平線(2)」の交点を基に、三角形の形状を形成します。
    6. １分足のチャート監視
        価格が「トレンドライン(1)」に触れた後、価格が反転する動き（トレンドラインより下に行った、もしくは触れたあとの上昇を指す）を示した場合、そのポイントで取引を開始（エントリー）します。
    （エントリー条件は、１分足でローソク足が一度、トレンドライン１に触れたあと、再度、１分足の終値がトレンドラインの上で確定したときの、次の始値です）
    7. 利確
        10pipに設定 TODO:将来的にトレールストップを実装する
    8. ストップロス
        エントリーポイントの直近の安値（極小値）よりも少し下の位置に、損切りのためのストップロス注文を設定
        上昇トレンドラインの起点となっている安値（極小値）のうち、最も近い極小値を直近安値と定義
    """
    def __init__(self):
        self.last_pivots_high = []
        self.last_pivots_low = []        

    def prepare_data(self, df):
        df["EMA50"] = df["5min_close"].ewm(span=50, adjust=False).mean()
        return df
    
    def calculate_pl(self, symbol, position, lot_size, entry_rate, exit_rate, spread, usd_jpy_rate=146):
        if position == "long":
            entry_rate_with_spread = entry_rate + spread
            exit_rate_with_spread = exit_rate
        elif position == "short":
            entry_rate_with_spread = entry_rate
            exit_rate_with_spread = exit_rate + spread
        else:
            raise ValueError("Invalid position type. Choose 'long' or 'short'.")
        
        value_difference = entry_rate_with_spread - exit_rate_with_spread
        
        # For pairs like EURUSD
        if symbol[-3:] != "JPY":
            return lot_size * value_difference * usd_jpy_rate
        
        # For pairs like USDJPY
        elif symbol[:3] == "USD":
            return lot_size * value_difference
        
        # For cross currency pairs like EURJPY
        else:
            return lot_size * value_difference * entry_rate_with_spread

    def calculate_trend_line(self, df, aim="longEntry", periods=100, num=2):
        # Use the last N periods for the calculation
        df_last_n = df.tail(periods)
        prices = df_last_n['5min_close'].values

        # Find pivots for highs and lows
        pivots_high, _ = find_peaks(prices, distance=num)
        pivots_low, _ = find_peaks(-prices, distance=num)

        # Check if pivots have changed
        if len(pivots_high) != len(self.last_pivots_high) or np.any(pivots_high != self.last_pivots_high):
            self.last_pivots_high = pivots_high
    
        if len(pivots_low) != len(self.last_pivots_low) or np.any(pivots_low != self.last_pivots_low):
            self.last_pivots_low = pivots_low

        # For aim="longEntry", ensure that both the highs and lows are in an uptrend
        if aim == "longEntry":
            if len(pivots_high) < 2 or pivots_high[-1] <= pivots_high[-2]:
                return None
            if len(pivots_low) < 2 or pivots_low[-1] <= pivots_low[-2]:
                return None
            pivots = pivots_low

        # For aim="shortEntry", ensure that both the highs and lows are in a downtrend
        elif aim == "shortEntry":
            if len(pivots_high) < 2 or pivots_high[-1] >= pivots_high[-2]:
                return None
            if len(pivots_low) < 2 or pivots_low[-1] >= pivots_low[-2]:
                return None
            pivots = pivots_high

        # If not enough pivots, return None
        if len(pivots) < num:
            return None

        # Calculate trend line using least squares method
        y = prices[pivots]
        slope, intercept = np.polyfit(pivots, y, 1)
        trendline = slope * np.arange(len(df_last_n)) + intercept

        # Extend the trendline array to match the original dataframe
        trendline_full = np.full(len(df), np.nan)
        trendline_full[-len(trendline):] = trendline

        return trendline_full


    def check_entry_condition(self, data_1min, trendline, i, price_point):
        trendline_value = trendline[-1]
        # print(f'trendline_value {trendline_value}')
        if price_point == "low":
            condition = data_1min['close'].iloc[i-1] <= trendline_value and data_1min['close'].iloc[i] > trendline_value
        else:
            condition = data_1min['close'].iloc[i-1] >= trendline_value and data_1min['close'].iloc[i] < trendline_value
        return condition


    def trade_conditions_func(self, df, i, portfolio, lot_size=10000, aim="longEntry"):
        take_profit_pips = 0.0010
        close = df.iloc[i]['close']
        
        if 'spread' in df.columns:
            spread = df.iloc[i]['spread']
        else:
            spread = 5

        if portfolio['position'] == 'long':

            if close >= portfolio['take_profit'] or close <= portfolio['stop_loss']:
                portfolio['stop_loss'] = None
                portfolio['profit'] = self.calculate_pl("EURUSD", "long", lot_size, portfolio['entry_price'], close, spread)
                return 'exit_long'


        trendline = self.calculate_trend_line(df, aim)
        if self.check_entry_condition(df, trendline, i, aim):
            portfolio['entry_price'] = close
            if aim == "longEntry":
                portfolio['take_profit'] = portfolio['entry_price'] + take_profit_pips
                portfolio['stop_loss'] = self.last_pivots_low[-1] - 0.0001
            else:
                portfolio['take_profit'] = portfolio['entry_price'] - take_profit_pips
                portfolio['stop_loss'] = self.last_pivots_high[-1] + 0.0001
            return 'entry_long' if aim == "longEntry" else 'entry_short'
        else:
            return None


