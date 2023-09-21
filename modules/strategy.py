from scipy.signal import find_peaks
import numpy as np

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
            ロング: 連続する安値(高値)の上昇ポイントを特定
            ショート: 連続する高値(安値)の下降ポイントを特定
        トレンドラインの延長線上に、将来クロスするポイントを見つける

    - 最新の高値の特定
        ５分足のチャートでの最新の高値を特定

    - 水平線(2)の作成
        水平線の定義 ※ロングの例
        レジスタンスライン: 価格が上昇を試みるもののその都度反転して下落する価格レベルで、売り注文が集中していることを示す
        サポートライン: 価格が下落を試みるもののその都度反転して上昇する価格レベルで、買い注文が集中していることを示す

    - アセンディングトライアングル・ディセンディングトライアングルの検知
        「トレンドライン(1)」と「水平線(2)」の交点を基に、三角形の形成を検知

    - 1分足の監視・トレードロジック
        トレンドの初動を取りたい
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
        take_profit_pips: 利確幅
        stop_loss_pips: ストップロス幅
        base_spread_pips: スプレッドの基準値
        df_sliced_period: トレンドライン・水平線の計算に使うデータ期間
        distance: 極大値・極小値の間にあるローソク足の最低距離
        pivot_count: トレンドラインの計算に使う直近極値の数
        horizontal_distance: 水平線を検出するための最低距離
        horizontal_threshold: 水平線を検出するための閾値
        entry_horizontal_distance: (エントリー条件における水平線の許容距離
    """
    def __init__(self, symbol, allow_long=True, allow_short=False, params=None):
        self.last_max_value = 0
        self.last_min_value = 0
        self.pip_value = 0.01 if 'JPY' in symbol else 0.0001
        self.allow_long = allow_long
        self.allow_short = allow_short
        
        # Setting values
        self.risk_reward_ratio = 1.2
        self.take_profit_pips = 0.0010  # 10 pips
        self.stop_loss_pips = 0.0015   # 15 pips
        self.base_spread_pips = 0.0005 # 5 pips
        self.df_sliced_period = 200
        self.distance = 15
        self.pivot_count = 4
        self.horizontal_distance = 10
        self.horizontal_threshold = 4
        self.entry_horizontal_distance = 0.0003 # 1 pips(0.0001 ~ 0.0003?)

        if params:
            for key, value in params.items():
                setattr(self, key, value)

    def detect_horizontal_lines(self, prices_high, prices_low):
        try:
            pivots_high, _ = find_peaks(prices_high, distance=self.horizontal_distance)
            pivots_low, _ = find_peaks(-prices_low, distance=self.horizontal_distance)
            
            combined_pivots = np.concatenate([prices_high[pivots_high], prices_low[pivots_low]])
            hist, bin_edges = np.histogram(combined_pivots, bins=len(combined_pivots))
            horizontal_lines = bin_edges[:-1][hist >= self.horizontal_threshold]
            return horizontal_lines
        except Exception as e:
            return []

    def calculate_trend_line(self, prices_high, prices_low, aim="longEntry"):
        # Find pivots for highs and lows
        pivots_high, _ = find_peaks(prices_high, distance=self.distance)
        pivots_low, _ = find_peaks(-prices_low, distance=self.distance)

        # For aim="longEntry", ensure that both the highs and lows are in an uptrend
        if aim == "longEntry":
            # if len(pivots_high) < 2 or prices_high[pivots_high[-1]] <= prices_high[pivots_high[-2]]:
            #     return None
            if len(pivots_low) < 2 or prices_low[pivots_low[-1]] <= prices_low[pivots_low[-2]]:
                return None
            prices = prices_low
            x = pivots_low

        # For aim="shortEntry", ensure that both the highs and lows are in a downtrend
        elif aim == "shortEntry":
            if len(pivots_high) < 2 or prices_high[pivots_high[-1]] >= prices_high[pivots_high[-2]]:
                return None
            # if len(pivots_low) < 2 or prices_low[pivots_low[-1]] >= prices_low[pivots_low[-2]]:
            #     return None
            prices = prices_high
            x = pivots_high

        # Update pivots
        self.last_max_value = prices_high[pivots_high[-1]]
        self.last_min_value = prices_low[pivots_low[-1]]
        
        # Use the last pivots-count to calculate the support line
        y = prices[x[-self.pivot_count:]]
        slope, intercept = np.polyfit(x[-self.pivot_count:], y, 1)
        trendline = slope * np.arange(len(prices)) + intercept
        return trendline
    
    def determine_trend_direction(self, df, i, period=200):
        """
        Determine the trend direction based on Dow Theory.
        
        Parameters:
        - df: DataFrame containing the price data.
        - period: The period to consider for the trend determination.
        
        Returns:
        - 'up': If both highs and lows are increasing.
        - 'down': If both highs and lows are decreasing.
        - 'range': If neither of the above conditions is met.
        """
        # Slice the dataframe based on the given period
        if i < period:
            df_sliced = df.iloc[:i+1]
        else:
            df_sliced = df.iloc[i-period+1:i+1]
        
        # Get the high and low prices
        prices_high = df_sliced['high'].values
        prices_low = df_sliced['low'].values
        
        # Find the peaks for highs and lows
        pivots_high, _ = find_peaks(prices_high, distance=30)
        pivots_low, _ = find_peaks(-prices_low, distance=30)
        
        # Check the trend direction
        if len(pivots_high) >= 2 and prices_high[pivots_high[-1]] > prices_high[pivots_high[-2]] and \
            len(pivots_low) >= 2 and prices_low[pivots_low[-1]] > prices_low[pivots_low[-2]]:
            return 'up'
        elif len(pivots_high) >= 2 and prices_high[pivots_high[-1]] < prices_high[pivots_high[-2]] and \
            len(pivots_low) >= 2 and prices_low[pivots_low[-1]] < prices_low[pivots_low[-2]]:
            return 'down'
        else:
            return 'range'
    
    def check_candle_size(self, aim, opens, closes):
        if len(closes) < 2:
            return False

        current_close = closes[-1]
        current_open = opens[-1]
        previous_close = closes[-2]
        previous_open = opens[-2]
        
        current_body_size = abs(current_close - current_open)
        previous_body_size = abs(previous_close - previous_open)
               
        if aim == "longEntry":
            if current_close > current_open and current_body_size > previous_body_size:
                return True
        
        elif aim == "shortEntry":
            if current_close < current_open and current_body_size > previous_body_size:
                return True

        return False

    def check_entry_condition(self, opens, closes, highs, lows, aim):
        trendline = self.calculate_trend_line(highs, lows, aim)

        if trendline is None:
            return False
        
        trendline_value = trendline[-1]

        if aim == "longEntry":
            condition = lows[-2] <= trendline_value and closes[-1] > trendline_value and self.check_candle_size(aim, opens, closes)
        else:
            condition = highs[-2] >= trendline_value and closes[-1] < trendline_value and self.check_candle_size(aim, opens, closes)
        return condition
    
    # The updated check_entry_condition_with_horizontal_line function
    def check_entry_condition_with_horizontal_line(self, opens, closes, highs, lows, aim):
        
        # Detect horizontal lines
        horizontal_lines = self.detect_horizontal_lines(highs, lows)
        
        # If no horizontal lines are detected, return False
        if len(horizontal_lines) == 0:
            return False
        
        # First, check the existing entry condition
        if not self.check_entry_condition(opens, closes, highs, lows, aim):
            return False

        # Check for nearby horizontal lines based on the aim (long/short)
        if aim == "longEntry":
            # Check if there's a horizontal line within entry_horizontal_distance above the current price
            for line in horizontal_lines:
                if closes[-1] <= line <= closes[-1] + self.entry_horizontal_distance:
                    return True

        elif aim == "shortEntry":
            # Check if there's a horizontal line within entry_horizontal_distance below the current price
            for line in horizontal_lines:
                if closes[-1] - self.entry_horizontal_distance <= line <= closes[-1]:
                    return True

        return False
        
    def trade_conditions_func(self, df, i, portfolio, closes, spreads):
        close = closes[i]
        spread_pips = spreads[i] * self.pip_value

        if self.base_spread_pips > 0 and spread_pips >= self.base_spread_pips * 2:
            # print(f"Warning: Spread is unusually high at {df.iloc[i]['spread']}pips. Skipping trade at index {i}.")
            return None

        # Exit
        if portfolio['position'] == 'long':
            if close >= portfolio['take_profit'] or close <= portfolio['stop_loss']:
                portfolio['pips'] = (close - portfolio['entry_price']) * (1 / self.pip_value) - spread_pips
                print(f"Long pips: {portfolio['pips']:.5f}, entry: {portfolio['entry_price']}, close: {close}, spread: {spread_pips}")
                return 'exit_long'

        elif portfolio['position'] == 'short':
            if close <= portfolio['take_profit'] or close >= portfolio['stop_loss']:
                portfolio['pips'] = (portfolio['entry_price'] - close) * (1 / self.pip_value) + spread_pips
                print(f"Short pips: {portfolio['pips']:.5f}, entry: {portfolio['entry_price']}, close: {close}, spread: {spread_pips}")
                return 'exit_short'

        # Entry
        else:
            if i < self.df_sliced_period:
                df_sliced = df.iloc[:i+1]
            else:
                df_sliced = df.iloc[i-self.df_sliced_period+1:i+1]
            
            opens_sliced = df_sliced['open'].values
            closes_sliced = df_sliced['close'].values
            highs_sliced = df_sliced['high'].values
            lows_sliced = df_sliced['low'].values

            # trend_direction = self.determine_trend_direction(df, i)
            # print(f'{i}: {trend_direction}')

            if self.check_entry_condition_with_horizontal_line(opens_sliced, closes_sliced, highs_sliced, lows_sliced, "longEntry"):
                if self.allow_long:
                    portfolio['take_profit'] = close + (self.stop_loss_pips * self.risk_reward_ratio)
                    portfolio['stop_loss'] = self.last_min_value - self.stop_loss_pips
                    portfolio['entry_price'] = close
                    return 'entry_long'

            elif self.check_entry_condition_with_horizontal_line(opens_sliced, closes_sliced, highs_sliced, lows_sliced, "shortEntry"):
                if self.allow_short:
                    portfolio['take_profit'] = close - (self.stop_loss_pips * self.risk_reward_ratio)
                    portfolio['stop_loss'] = self.last_max_value + self.stop_loss_pips
                    portfolio['entry_price'] = close
                    return 'entry_short'