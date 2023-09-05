import pandas as pd
from ta.trend import EMAIndicator
from scipy.signal import find_peaks
import numpy as np

class TradingStrategy:
    def __init__(self, lot_size=10000):
        self.lot_size = lot_size

    def prepare_data(self, df):
        # Calculate moving averages
        df["EMA50"] = EMAIndicator(df["5min_close"], window=50, fillna=False).ema_indicator()
        return df
    
    def trend_direction(self, df, i):
        if i == 0:  # Skip the first row
            return None
        # Calculate the trend direction based on the angle of the EMA
        if i < 1:
            return None
        angle = np.arctan((df.loc[i, "EMA50"] - df.loc[i-1, "EMA50"]) / 1) * (180 / np.pi)
        
        # Check trend direction
        if angle > 0:
            return "up"
        elif angle < 0:
            return "down"
        else:
            return None
        
    def is_strong_trend(self, angle, threshold=1):
        # Determine if it's a strong trend based on the angle
        return abs(angle) > threshold
    
    def calculate_resistance_zone(self, df, start, end, buffer=1, rebound_threshold=2):
        data = df['5min_close'].iloc[start:end+1].values
        maxima_indices, _ = find_peaks(data)
        maxima_values = data[maxima_indices]
        upper_bounds = maxima_values + buffer
        lower_bounds = maxima_values - buffer
        rebound_counts = np.sum((lower_bounds[:, np.newaxis] < data) & (data < upper_bounds[:, np.newaxis]), axis=1)
        valid_indices = np.where(rebound_counts >= rebound_threshold)[0]
        valid_lower_bounds = lower_bounds[valid_indices]
        valid_upper_bounds = upper_bounds[valid_indices]
        resistance_zones = list(zip(valid_lower_bounds, valid_upper_bounds))
        return resistance_zones

    def is_price_in_resistance(self, resistance_zones, price):
        for zone in resistance_zones:
            if zone[0] <= price <= zone[1]:
                return True
        return False

    def is_higher_lows(self, df, i):
        if i < 2:
            return False
        return df.loc[i, "5min_close"] > df.loc[i-1, "5min_close"] and df.loc[i-1, "5min_close"] > df.loc[i-2, "5min_close"]

    # trade logic
    def trade_conditions_func(self, df, i, portfolio):
        if i == 0:  # Skip the first row
            return None

        close = df.loc[i, 'close']
        close5 = df.loc[i, '5min_close']
        spread = df.loc[i, 'spread']

        resistance_zones = self.calculate_resistance_zone(df, 0, i)
        in_resistance = self.is_price_in_resistance(resistance_zones, close5)
        higher_lows = self.is_higher_lows(df, i)

        # Spread conversion to currency unit (1 pip = 0.01 yen)
        spread_cost = spread * 0.01 * self.lot_size

        # Profit and loss thresholds
        TAKE_PROFIT = 0.005 * portfolio['entry_price'] if portfolio['entry_price'] else 0
        STOP_LOSS = -0.01 * portfolio['entry_price'] if portfolio['entry_price'] else 0

        if portfolio['position'] == 'long':
            profit = (close - portfolio['entry_price']) - spread_cost
            if profit > TAKE_PROFIT or profit < STOP_LOSS:
                return 'exit_long'
              
        # elif portfolio['position'] == 'short':
        #     profit = (portfolio['entry_price'] - close) - spread_cost
        #     if profit > TAKE_PROFIT or profit < STOP_LOSS:
        #         return 'exit_short'

        # Entry conditions
        elif in_resistance and higher_lows:
            return 'entry_long'
          
        # No entry short condition defined in the requirements, so I am omitting it for now.
        #elif (conditions for short):
        #    return 'entry_short'
        
        else:
            return None
