import numpy as np
import pandas as pd
from scipy.signal import find_peaks

class TradingStrategy:
    """
    設定値
        risk_reward_ratio: リスクリワード（損失に対する利益の比率）
        stop_loss_pips: ストップロス幅
        base_spread_pips: スプレッドの基準値
        df_sliced_period: 計算に使うデータ期間の範囲
        distance: 極大値・極小値の間にあるローソク足の最低距離
        candle_size_pips: 大陽線・大陰線の基準とする最低値幅
    """
    def __init__(self, params=None):
        # Setting values
        self.symbol = 'USDJPY'
        self.risk_reward_ratio = 1.0
        self.stop_loss_pips = 0.10   # 10 pips
        self.base_spread_pips = 0.03 # 3 pips
        self.df_sliced_period = 500
        self.distance = 7,
        self.candle_size_pips: 0.05

        if params:
            for key, value in params.items():
                setattr(self, key, value)

        self.pip_value = 0.01 if 'JPY' in self.symbol else 0.0001
        self.trade_results = []

        # Set up
        self.conditions = self.init_conditions()

    def init_conditions(self):
        return {
            'last_max_value': 0, # 直近高値
            'last_min_value': 0, # 直近安値
            'highest_price': 0,  # 最高値
            'lowest_price': 0,   # 最安値
            'trend_reversal_line': 0,      #  戻り高値 => (下降から上昇への)トレンド転換ライン
            'trend_reversal_line_short': 0 #  押し安値 => (上昇から下降への)トレンド転換ライン
        }

    def get_trade_results(self):
        return self.trade_results
    
    def zigzag_calculate(self, highs, lows):
        peaks, _ = find_peaks(highs, distance=self.distance)
        valleys, _ = find_peaks(-lows, distance=self.distance)
        return peaks, valleys

    def define_trend_reversal_line(self, highs, lows):
        pivots_high, pivots_low = self.zigzag_calculate(highs, lows)
        consecutive_descendings = 0
        min_length = min(len(pivots_high), len(pivots_low))
        
        for i in range(1, min_length):
            if (highs[pivots_high[i]] < highs[pivots_high[i - 1]]) and (lows[pivots_low[i]] < lows[pivots_low[i - 1]]):
                consecutive_descendings += 1
                
                if consecutive_descendings >= 5:
                    lowest_low_point = min(pivots_low, key=lambda x: lows[x])
                    corresponding_high_idx = pivots_low.tolist().index(lowest_low_point)

                    if corresponding_high_idx < len(pivots_high):
                        corresponding_high_point = pivots_high[corresponding_high_idx]
                        self.conditions['last_min_value'] = lows[pivots_low][-1]
                        self.conditions['lowest_price'] = lows[lowest_low_point]
                        return highs[corresponding_high_point]
            else:
                consecutive_descendings = 0

        return None
    
    def update_trend_reversal_line(self, highs, lows):
        pivots_high, pivots_low = self.zigzag_calculate(highs, lows)
        lowest_low_point = min(pivots_low, key=lambda x: lows[x])
        corresponding_high_idx = pivots_low.tolist().index(lowest_low_point)

        if corresponding_high_idx < len(pivots_high):
            corresponding_high_point = pivots_high[corresponding_high_idx]
            self.conditions['last_min_value'] = lows[pivots_low][-1]
            self.conditions['lowest_price'] = lows[lowest_low_point]
            return highs[corresponding_high_point]
 
    def define_trend_reversal_line_short(self, highs, lows):
        pivots_high, pivots_low = self.zigzag_calculate(highs, lows)
        consecutive_ascendings = 0
        min_length = min(len(pivots_high), len(pivots_low))
        
        for i in range(1, min_length):
            if (highs[pivots_high[i]] > highs[pivots_high[i - 1]]) and (lows[pivots_low[i]] > lows[pivots_low[i - 1]]):
                consecutive_ascendings += 1
                
                if consecutive_ascendings >= 5:
                    highest_high_point = max(pivots_high, key=lambda x: highs[x])
                    corresponding_low_idx = pivots_high.tolist().index(highest_high_point)

                    if corresponding_low_idx < len(pivots_low):
                        corresponding_low_point = pivots_low[corresponding_low_idx]
                        self.conditions['last_max_value'] = highs[pivots_high][-1]
                        self.conditions['highest_price'] = highs[highest_high_point]
                        return lows[corresponding_low_point]
            else:
                consecutive_ascendings = 0

        return None
    
    def update_trend_reversal_line_short(self, highs, lows):
        pivots_high, pivots_low = self.zigzag_calculate(highs, lows)
        highest_high_point = max(pivots_high, key=lambda x: highs[x])
        corresponding_low_idx = pivots_high.tolist().index(highest_high_point)

        if corresponding_low_idx < len(pivots_low):
            corresponding_low_point = pivots_low[corresponding_low_idx]
            self.conditions['last_max_value'] = highs[pivots_high][-1]
            self.conditions['highest_price'] = highs[highest_high_point]
            return lows[corresponding_low_point]

    def is_long_entry_condition(self, opens, highs, lows, closes, use_ema_filter=True):
        trend_reversal_line = None

        if self.conditions['last_min_value'] == 0 and self.conditions['last_max_value'] == 0:
            trend_reversal_line = self.define_trend_reversal_line(highs, lows)
        elif self.conditions['lowest_price'] > closes[-1]:
            trend_reversal_line = self.update_trend_reversal_line(highs, lows)
        
        if trend_reversal_line is None and self.conditions['trend_reversal_line'] == 0:
            return False
        
        if (self.conditions['trend_reversal_line'] != trend_reversal_line and
            trend_reversal_line is not None):
            self.conditions['trend_reversal_line'] = trend_reversal_line

        ema100 = pd.Series(closes).ewm(span=100, adjust=False).mean().values
        if use_ema_filter and closes[-1] <= ema100[-1]:
            return False

        candle_body = abs(closes[-1] - opens[-1])
        candle_wick = max(highs[-1] - max(opens[-1], closes[-1]), min(opens[-1], closes[-1]) - lows[-1])
        
        avg_candle_body_last_20 = sum([abs(closes[i] - opens[i]) for i in range(-20, 0)]) / 20
        
        if (closes[-1] > self.conditions['trend_reversal_line'] and
            candle_body > avg_candle_body_last_20 and
            candle_wick <= (0.2 * candle_body) and
            candle_body >= self.candle_size_pips):
            return True

        return False
    
    def is_short_entry_condition(self, opens, highs, lows, closes, use_ema_filter=True):
        trend_reversal_line = None

        if self.conditions['last_min_value'] == 0 and self.conditions['last_max_value'] == 0:
            trend_reversal_line = self.define_trend_reversal_line_short(highs, lows)
        elif self.conditions['highest_price'] < closes[-1]:
            trend_reversal_line = self.update_trend_reversal_line_short(highs, lows)
        
        if trend_reversal_line is None and self.conditions['trend_reversal_line_short'] == 0:
            return False
        
        if (self.conditions['trend_reversal_line_short'] != trend_reversal_line and
            trend_reversal_line is not None):
            self.conditions['trend_reversal_line_short'] = trend_reversal_line

        ema100 = pd.Series(closes).ewm(span=100, adjust=False).mean().values
        if use_ema_filter and closes[-1] >= ema100[-1]:
            return False

        candle_body = abs(closes[-1] - opens[-1])
        candle_wick = max(highs[-1] - max(opens[-1], closes[-1]), min(opens[-1], closes[-1]) - lows[-1])
        
        avg_candle_body_last_20 = sum([abs(closes[i] - opens[i]) for i in range(-20, 0)]) / 20
        
        if (closes[-1] < self.conditions['trend_reversal_line_short'] and
            candle_body > avg_candle_body_last_20 and
            candle_wick <= (0.2 * candle_body) and
            candle_body >= self.candle_size_pips):
            return True

        return False
     
    def trade_logic_trend_reversal(self, df, i, portfolio, closes, spreads):
        close = closes[i]
        spread_pips = spreads[i] * self.pip_value

        if self.base_spread_pips > 0 and spread_pips >= self.base_spread_pips * 2:
            # print(f"Warning: Spread is unusually high at {df.iloc[i]['spread']}pips. Skipping trade at index {i}.")
            return None

        # Exit
        if portfolio['position'] == 'long':
            if close >= portfolio['take_profit'] or close <= portfolio['stop_loss']:
                portfolio['pips'] = (close - portfolio['entry_price']) * (1 / self.pip_value) - spread_pips

                action = 'exit_long'
                self.trade_results.append({
                    'index': i,
                    'action': action,
                    'entry_price': portfolio['entry_price'],
                    'reversal_price': self.conditions['trend_reversal_line'],
                    'take_profit_price': portfolio['take_profit'],
                    'stop_loss_price': portfolio['stop_loss'],
                    'exit_price': close,
                    'gained_pips': portfolio['pips']
                })
                self.conditions = self.init_conditions()
                return action

        elif portfolio['position'] == 'short':
            if close <= portfolio['take_profit'] or close >= portfolio['stop_loss']:
                portfolio['pips'] = (portfolio['entry_price'] - close) * (1 / self.pip_value) + spread_pips

                action = 'exit_short'
                self.trade_results.append({
                    'index': i,
                    'action': action,
                    'entry_price': portfolio['entry_price'],
                    'reversal_price': self.conditions['trend_reversal_line_short'],
                    'take_profit_price': portfolio['take_profit'],
                    'stop_loss_price': portfolio['stop_loss'],
                    'exit_price': close,
                    'gained_pips': portfolio['pips']
                })
                self.conditions = self.init_conditions()
                return action

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
            
            if self.is_long_entry_condition(opens_sliced, highs_sliced, lows_sliced, closes_sliced, True):

                portfolio['take_profit'] = close + (self.stop_loss_pips * self.risk_reward_ratio)
                portfolio['stop_loss'] = self.conditions['last_min_value'] - self.stop_loss_pips
                portfolio['entry_price'] = close
                portfolio['reversal_price'] = self.conditions['trend_reversal_line']
                portfolio['position'] = 'long'

                action = 'entry_long'
                self.trade_results.append({
                    'index': i,
                    'action': action,
                    'entry_price': close,
                    'reversal_price': self.conditions['trend_reversal_line'],
                    'take_profit_price': portfolio['take_profit'],
                    'stop_loss_price': portfolio['stop_loss'],
                    'exit_price': 0,
                    'gained_pips': 0
                })
                return action
            
            elif self.is_short_entry_condition(opens_sliced, highs_sliced, lows_sliced, closes_sliced, True):


                portfolio['take_profit'] = close - (self.stop_loss_pips * self.risk_reward_ratio)
                portfolio['stop_loss'] = self.conditions['last_max_value'] + self.stop_loss_pips
                portfolio['entry_price'] = close
                portfolio['reversal_price'] = self.conditions['trend_reversal_line_short']
                portfolio['position'] = 'short'

                action = 'entry_short'
                self.trade_results.append({
                    'index': i,
                    'action': action,
                    'entry_price': close,
                    'reversal_price': self.conditions['trend_reversal_line_short'],
                    'take_profit_price': portfolio['take_profit'],
                    'stop_loss_price': portfolio['stop_loss'],
                    'exit_price': 0,
                    'gained_pips': 0
                })
                return action
          