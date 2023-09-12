from scipy.signal import find_peaks
import numpy as np
from datetime import datetime

class TradingStrategy:
    """
    トレードロジック
    使用データ: 1分足データを取得
    - 疑似的に上位足チャート参照
        1分足の極大値・極小値の距離を最低でも5本以上開ける

    - トレンドライン(1)の作成
        上昇する安値のポイントを結ぶ直線を描く (この直線を「トレンドライン(1)」と呼ぶ)
        ※トレンドラインの定義：（上昇トレンドなら極小値のピークの切り上がり）を結んだもの
        トレンドライン発生の定義
            ロング: 連続する高値・安値の上昇イントを特定
            ショート: 連続する高値・安値の下降ポイントを特定
        トレンドラインの延長線上に、将来クロスするポイントを見つける

    - 最新の高値の特定
        ５分足のチャートでの最新の高値を特定

    - 水平線(2)の作成 ※未実装
        最新の高値から水平に直線を引く (この直線を「水平線(2)」と呼ぶ)

    - 三角形の形状の作成 ※未実装
        「トレンドライン(1)」と「水平線(2)」の交点を基に、三角形の形状を形成

    - 1分足の監視
        価格が「トレンドライン(1)」に触れた後、価格が反転する動き（トレンドラインより下に行った、もしくは触れたあとの上昇を指す）を示した場合、そのポイントで取引を開始（エントリー）します。
    （エントリー条件は、１分足でローソク足が一度、トレンドライン１に触れたあと、再度、１分足の終値がトレンドラインの上で確定したときの、次の始値）
    いわゆる価格とトレンドラインのゴールデンクロスとなる状態

    - 利確
        - 固定値 10pips に設定
        - リスクリワードに合わせてストップから利確目標を計算

    - ストップロス
        ロング: エントリーポイントの直近の極小値よりも少し下の位置に、ストップロスを設定（ストップ狩りを回避するため）
        ショート: エントリーポイントの直近の極大値よりも少し上の位置に、ストップロスを設定

    設定値
        risk_reward_ratio: リスクリワード（損失に対する利益の比率）
        stop_loss_point: ストップロス幅
        distance: 極大値・極小値の間にあるローソク足の最低距離
        pivot_count: トレンドラインの計算に使う直近極値の数
        period: トレンドラインの計算に使うデータ期間
    """
    def __init__(self, allow_short=False):
        self.last_max_value = 0
        self.last_min_value = 0
        self.allow_short = allow_short
        
        # Setting values
        self.risk_reward_ratio = 2.0
        self.stop_loss_point = 0.0001
        self.period = 300
        self.distance = 60
        self.pivot_count = 3

    def prepare_data(self, df):
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
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

    def calculate_trend_line(self, df, aim="longEntry"):
        # Use the last N periods for the calculation
        prices_high = df['high'].values
        prices_low = df['low'].values

        # Find pivots for highs and lows
        pivots_high, _ = find_peaks(prices_high, distance=self.distance)
        pivots_low, _ = find_peaks(-prices_low, distance=self.distance)

        # For aim="longEntry", ensure that both the highs and lows are in an uptrend
        if aim == "longEntry":
            if len(pivots_high) < 2 or prices_high[pivots_high[-1]] <= prices_high[pivots_high[-2]]:
                return None
            if len(pivots_low) < 2 or prices_low[pivots_low[-1]] <= prices_low[pivots_low[-2]]:
                return None
            prices = prices_low
            x = pivots_low

        # For aim="shortEntry", ensure that both the highs and lows are in a downtrend
        elif aim == "shortEntry":
            if len(pivots_high) < 2 or prices_high[pivots_high[-1]] >= prices_high[pivots_high[-2]]:
                return None
            if len(pivots_low) < 2 or prices_low[pivots_low[-1]] >= prices_low[pivots_low[-2]]:
                return None
            prices = prices_high
            x = pivots_high

        # Update pivots
        self.last_max_value = prices_high[pivots_high[-1]]
        self.last_min_value = prices_low[pivots_low[-1]]    
        
        # Use the last pivots-count to calculate the support line
        y = prices[x[-self.pivot_count:]]
        slope, intercept = np.polyfit(x[-self.pivot_count:], y, 1)
        trendline = slope * np.arange(len(df)) + intercept
        return trendline

    def check_entry_condition(self, df, aim):
        trendline = self.calculate_trend_line(df, aim)

        if trendline is None:
            return False
        
        trendline_value = trendline[-1]

        if aim == "longEntry":
            condition = df['low'].iloc[-2] <= trendline_value and df['close'].iloc[-1] > trendline_value
        else:
            condition = df['high'].iloc[-2] >= trendline_value and df['close'].iloc[-1] < trendline_value
        return condition

    def trade_conditions_func(self, symbol, df, i, portfolio, lot_size=0.1):
        close = df.iloc[i]['close']
        
        if 'spread' in df.columns:
            spread = df.iloc[i]['spread']
        else:
            spread = 5

        if i < self.period:
            df_sliced = df.iloc[:i+1]
        else:
            df_sliced = df.iloc[i-self.period+1:i+1]

        # Exit
        if portfolio['position'] == 'long':
            if close >= portfolio['take_profit'] or close <= portfolio['stop_loss']:
                portfolio['stop_loss'] = None
                portfolio['profit'] = self.calculate_pl(symbol, "long", lot_size, portfolio['entry_price'], close, spread)
                return 'exit_long'
            
        elif portfolio['position'] == 'short':
            if close <= portfolio['take_profit'] or close >= portfolio['stop_loss']:
                portfolio['stop_loss'] = None
                portfolio['profit'] = self.calculate_pl(symbol, "short", lot_size, portfolio['entry_price'], close, spread)
                return 'exit_short'

        # Entry
        if self.check_entry_condition(df_sliced, "longEntry"):
            stop_loss = self.last_min_value - self.stop_loss_point
            stop_loss_distance = close - stop_loss
            portfolio['take_profit'] = close + (stop_loss_distance * self.risk_reward_ratio)
            portfolio['stop_loss'] = stop_loss
            portfolio['entry_price'] = close
            return 'entry_long' 

        elif self.allow_short:
            if self.check_entry_condition(df_sliced, "shortEntry"):
                stop_loss = self.last_max_value + self.stop_loss_point
                stop_loss_distance = stop_loss - close
                portfolio['take_profit'] = close - (stop_loss_distance * self.risk_reward_ratio)
                portfolio['stop_loss'] = stop_loss
                portfolio['entry_price'] = close
                return 'entry_short'

        else:
            return None