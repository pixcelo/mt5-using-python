import sys
sys.path.append('d:\\dev\\mt5-python')

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from modules import TradingStrategy
from modules import TriangleStrategy

import matplotlib.pyplot as plt

def plot_df(df, buy_entries=[], buy_exits=[], sell_entries=[], sell_exits=[]):
    plt.figure(figsize=(16,4))
    
    # Convert DataFrame columns and indices to numpy arrays for faster operations
    closes = df['close'].values
    indices = df.index.values
    
    # Plotting the close prices
    plt.plot(indices, closes, label='Close', alpha=0.7)
    
    # Plotting buy and sell points
    plt.scatter(indices[buy_entries], closes[buy_entries], marker='^', color='g', label='Buy Entry', alpha=0.7)
    plt.scatter(indices[buy_exits], closes[buy_exits], marker='v', color='darkgreen', label='Buy Exit', alpha=0.7)
    plt.scatter(indices[sell_entries], closes[sell_entries], marker='v', color='r', label='Sell Entry', alpha=0.7)
    plt.scatter(indices[sell_exits], closes[sell_exits], marker='^', color='darkred', label='Sell Exit', alpha=0.7)
    
    plt.title('Close Price Over Time')
    plt.xlabel('Time')
    plt.ylabel('Close Price')
    plt.legend()
    plt.grid(True)
    plt.show()

def filter_dataframe_by_date(df, start_date=None, end_date=None):
    datetime_column_name = 'time'
    if start_date:
        df = df[df[datetime_column_name] >= start_date]
    if end_date:
        df = df[df[datetime_column_name] <= end_date]
    return df

# Initialize portfolio state
def init_portfolio():
    return {
        'position': None,  # "long" or "short"
        'entry_price': None,
        'entry_point': 0,
        'trailing_stop': 0,
        'take_profit': None,
        'stop_loss': None,
        'profit': 0
    }

def trade_logic(df, trade_conditions_func, pips):
    df = df.reset_index(drop=True)

    closes = df['close'].values
    spreads = df['spread'].values

    trade_results = {
        'pips': [],
        'long_pips': [],
        'short_pips': [],
        'buy_entries': [],
        'buy_exits': [],
        'sell_entries': [],
        'sell_exits': []
    }

    portfolio = init_portfolio()

    for i in range(0, len(df)):
        pips = 0

        action = trade_conditions_func(df, i, portfolio, closes, spreads)

        if portfolio['position'] is not None:
            if action == 'exit_long':
                trade_results['pips'].append(portfolio['pips'])
                trade_results['long_pips'].append(portfolio['pips'])
                trade_results['buy_exits'].append(i)
                portfolio = init_portfolio()

            if action == 'exit_short':
                trade_results['pips'].append(portfolio['pips'])
                trade_results['short_pips'].append(portfolio['pips'])
                trade_results['sell_exits'].append(i)
                portfolio = init_portfolio()

            else:
                trade_results['pips'].append(pips)
        
        elif action == 'entry_long':
            trade_results['pips'].append(pips)
            trade_results['buy_entries'].append(i)
            portfolio['position'] = 'long'

        elif action == 'entry_short':
            trade_results['pips'].append(pips)
            trade_results['sell_entries'].append(i)
            portfolio['position'] = 'short'

        else:
            trade_results['pips'].append(pips)

    return trade_results


# Backtest

# 1pips = 0.01 point
settings_triangle = { 
    'risk_reward_ratio': 1.3,
    'take_profit_pips': 0.15,
    'stop_loss_pips': 0.10,
    'base_spread_pips': 0.03,
    'df_sliced_period': 200,
    'distance': 15,
    'pivot_count': 3,
    'horizontal_distance': 60,
    'horizontal_threshold': 3,
    'entry_horizontal_distance': 0.01, # 0.01 ~ 0.03 ?
}

# 1pips = 0.0001 point
# settings = {
#     'risk_reward_ratio': 1.2,
#     'take_profit_pips': 0.0010,
#     'stop_loss_pips': 0.0015,
#     'base_spread_pips': 0.0005,
#     'df_sliced_period': 200,
#     'distance': 15,
#     'pivot_count': 4,
#     'horizontal_distance': 10,
#     'horizontal_threshold': 3,
#     'entry_horizontal_distance': 0.0002, # 0.0001 ~ 0.0003 ?
# }
# settings=None

settings_reversal_usdjpy = { 
    'symbol': 'USDJPY',
    'risk_reward_ratio': 1.0,
    'stop_loss_pips': 0.10,
    'base_spread_pips': 0.03,
    'df_sliced_period': 300,
    'distance': 5,
}

file_name = './csv/USDJPY_1_20220801_to_20230801.csv'
symbol = "USDJPY"
df = pd.read_csv(file_name)

if __name__ == '__main__':
    st_triangle = TriangleStrategy(symbol=symbol, allow_long=True, allow_short=True, params=settings_triangle)
    st_reversal = TradingStrategy(params=settings_reversal_usdjpy)

    # Filter data by date if required
    start_date = None
    end_date = None
    start_date = "2022-08-01"
    end_date = "2022-11-01"
    df = filter_dataframe_by_date(df, start_date, end_date)

    trade_conditions = [
        # (st_triangle.trade_conditions_func, "trend line trade"),
        (st_reversal.trade_logic_trend_reversal, "trend reversal")
    ]

    # Execute the trade logic
    for trade_condition, description in trade_conditions:
        result = trade_logic(df, trade_condition, st_triangle.base_spread_pips)

        # Plot using modified plot function
        plot_df(df, 
            result['buy_entries'], 
            result['buy_exits'], 
            result['sell_entries'], 
            result['sell_exits'],
        )

        result = st_reversal.get_trade_results()
        df_trade_results = pd.DataFrame(result)
        print(df_trade_results)
