from scipy.signal import find_peaks
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
import numpy as np

class TradingStrategy:
    def __init__(self, commission_rate=0.001, window=3000, threshold=0.05, lot_size=10000):
        self.COMMISSION_RATE = commission_rate
        self.window = window
        self.threshold = threshold
        self.lot_size = lot_size

    def prepare_data(self, df):
        # Calculate moving averages
        df['SMA20'] = df['close'].rolling(window=20).mean()
        df["EMA20"] = EMAIndicator(df["close"], window=20, fillna=False).ema_indicator()
        df["EMA200"] = EMAIndicator(df["close"], window=200, fillna=False).ema_indicator()
        df["EMA1200"] = EMAIndicator(df["close"], window=1200, fillna=False).ema_indicator()

        # degree
        df["EMA25"] = EMAIndicator(df["close"], window=25, fillna=False).ema_indicator()
        df["EMA100"] = EMAIndicator(df["close"], window=100, fillna=False).ema_indicator()
        df['EMA25_degrees'] = self.calculate_gradient_degrees(df['EMA25'], 25)
        df['EMA100_degrees'] = self.calculate_gradient_degrees(df['EMA100'], 25)

        rsi_indicator = RSIIndicator(close=df['close'])
        df['RSI'] = rsi_indicator.rsi()
        average_true_range = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=210 # 15min * 14
        )
        df['ATR'] = average_true_range.average_true_range()
        
        # Detect peaks (maxima) and valleys (minima) in the close prices for the 5min data using a distance parameter
        distance_threshold = 5
        peaks_resampled, _ = find_peaks(df['5min_close'], distance=distance_threshold)
        valleys_resampled, _ = find_peaks(-df['5min_close'], distance=distance_threshold)

        # Add the initial columns for maxima and minima
        df['maxima'] = np.nan
        df['minima'] = np.nan

        # Assign the close prices to the maxima and minima columns
        df.loc[df.index[peaks_resampled], 'maxima'] = df['5min_close'].iloc[peaks_resampled]
        df.loc[df.index[valleys_resampled], 'minima'] = df['5min_close'].iloc[valleys_resampled]

        # Forward fill (ffill) for maxima and minima
        df['maxima_ffill'] = df['maxima'].fillna(method='ffill')
        df['minima_ffill'] = df['minima'].fillna(method='ffill')

        # Linear interpolation for maxima and minima
        df['maxima_linear'] = df['maxima'].interpolate(method='linear')
        df['minima_linear'] = df['minima'].interpolate(method='linear')


        return df
    
    def calculate_gradient_degrees(self, series, periods):
        # Δyの計算
        delta_y = series - series.shift(periods)
        delta_y = delta_y.fillna(0)

        # Δxは期間
        delta_x = periods

        # arctan2で角度（ラジアン）を計算
        angle_rad = np.arctan2(delta_y, delta_x)

        # ラジアンから度数法に変換
        return np.degrees(angle_rad)

    # trade logic
    def trade_conditions_ema(self, df, i, portfolio):
        close = df.loc[i, 'close']
        ema20 = df.loc[i, 'EMA20']
        ema200 = df.loc[i, 'EMA200']
        ema1200 = df.loc[i, 'EMA1200']
        spread = df.loc[i, 'spread']

        prev_close = df.loc[i - 1, 'close'] if i > 0 else None
        prev_ema20 = df.loc[i - 1, 'EMA20'] if i > 0 else None
        prev_ema200 = df.loc[i - 1, 'EMA200'] if i > 0 else None
        prev_ema1200 = df.loc[i - 1, 'EMA1200'] if i > 0 else None

        # スプレッドを通貨単位に変換（1銭 = 0.01円）
        spread_cost = spread * 0.01 * self.lot_size  # 0.5銭なら50円

        # 利確と損切りの閾値
        TAKE_PROFIT = 100
        STOP_LOSS = -100

        if portfolio['position'] == 'long':
            profit = (close - portfolio['entry_price']) - spread_cost
            if profit > TAKE_PROFIT or profit < STOP_LOSS:
                return 'exit_long'    
        elif portfolio['position'] == 'short':
            profit = (portfolio['entry_price'] - close) - spread_cost
            if profit > TAKE_PROFIT or profit < STOP_LOSS:
                return 'exit_short'
        elif prev_close is not None and prev_ema200 is not None \
            and prev_close < prev_ema200 and close > ema200 \
            and ema200 > ema1200:
            return 'entry_long'        
        elif prev_close is not None and prev_ema200 is not None \
            and prev_close > prev_ema200 and close < ema200 \
            and ema200 < ema1200:
            return 'entry_short'
        else:
            return None
        

    # ワイコフ理論のディストリビューションのフェーズで同じ流れに乗る　エントリーは少なめ
    def trade_conditions_volume(self, df, i, portfolio):
        '''
        ディストリビューションの日には、株価が上がる一方で出来高は低下する
        もしくは価格が下がって出来高が上がる
        要は買い意欲は低く、売り圧力が強いということを出来高が教えてくれる

        （仕掛けのルール）※売りの場合
        3日前の株価(終値)は前日よりも高い
        3日前の出来高は前日よりも少ない
        1日前の株価(終値)は前日よりも高い
        1日前の出来高は前日よりも少ない
        今日の出来高は直近50日間の平均値の3倍よりも多い
        翌日に寄り付きで成行売りする
        '''
        close = df.loc[i, 'close']
        spread = df.loc[i, 'spread']

        # スプレッドを通貨単位に変換（1銭 = 0.01円）
        spread_cost = spread * 0.01 * self.lot_size  # 0.5銭なら50円

        # 利確と損切りの閾値
        TAKE_PROFIT = 100
        STOP_LOSS = -100

        if portfolio['position'] == 'long':
            profit = (close - portfolio['entry_price']) - spread_cost
            if profit > TAKE_PROFIT or profit < STOP_LOSS:
                return 'exit_long'    
        elif portfolio['position'] == 'short':
            profit = (portfolio['entry_price'] - close) - spread_cost
            if profit > TAKE_PROFIT or profit < STOP_LOSS:
                return 'exit_short'
        elif (
                i >= 4 and
                df['close'][i - 3] < df['close'][i - 4] and
                df['tick_volume'][i - 3] < df['tick_volume'][i - 4] and
                df['close'][i - 1] < df['close'][i - 2] and
                df['tick_volume'][i - 1] < df['tick_volume'][i - 2] and
                df['tick_volume'][i] > 3 * df['tick_volume'].rolling(window=50, min_periods=1).mean()[i]
            ):
            return 'entry_long'
        elif (
                i >= 4 and
                df['close'][i - 3] > df['close'][i - 4] and
                df['tick_volume'][i - 3] < df['tick_volume'][i - 4] and
                df['close'][i - 1] > df['close'][i - 2] and
                df['tick_volume'][i - 1] < df['tick_volume'][i - 2] and
                df['tick_volume'][i] > 3 * df['tick_volume'].rolling(window=50, min_periods=1).mean()[i]
            ):
            return 'entry_short'
        else:
            return None
        
