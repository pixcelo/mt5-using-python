from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
import MetaTrader5 as mt5
import numpy as np

class Trading:
    def __init__(self, symbol, lot_size=1, slippage=3):
        self.symbol = symbol
        self.lot_size = lot_size
        self.slippage = slippage

    def place_order(self, symbol, order_type, volume, price, stop_loss, take_profit):
        try:
            # 注文プロパティをセット
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": self.slippage, # point単位
                "magic": 234000,
                "comment": "python script open",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # 注文を実行
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise Exception("order_send failed, retcode={}".format(result.retcode))

            print("Order placed successfully!")
            return result

        except Exception as e:
            print("An error occurred while placing order:", str(e))
            return None

    def cancel_order(self, order_ticket):
        try:
            order = mt5.order_get(ticket=order_ticket)
            if order == None:
                raise Exception("Order not found")

            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order_ticket,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise Exception("Failed to cancel order, retcode={}".format(result.retcode))

            print("Order canceled successfully!")
            return result

        except Exception as e:
            print("An error occurred while canceling order:", str(e))
            return None

    def close_position(self, position_ticket):
        try:
            position = mt5.positions_get(ticket=position_ticket)
            if position == None:
                raise Exception("Position not found")
            
            pos = position[0]

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": pos.ticket,
                "price": mt5.symbol_info_tick(pos.symbol).ask if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).bid,
                "deviation": self.slippage,
                "magic": 234001,
                "comment": "python script close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise Exception("Failed to close position, retcode={}".format(result.retcode))

            print("Position closed successfully!")
            return result

        except Exception as e:
            print("An error occurred while closing position:", str(e))
        return None


    def get_position(self):
        # MT5のすべての開いているポジションを取得
        positions = mt5.positions_get()

        if positions == None:
            print('No positions found, error code:', mt5.last_error())
            return None

        # 特定の通貨ペアに対応するポジションを探す
        for position in positions:
            if position.symbol == self.symbol:
                # ポジションの詳細を辞書として返す
                return {
                    'id': position.ticket,
                    'symbol': position.symbol,
                    'type': position.type,
                    'volume': position.volume,
                    'price_open': position.price_open,
                    'sl': position.sl,
                    'tp': position.tp,
                    'profit': position.profit,
                    # 他の必要な属性...
                }

        return None
    
    def prepare_data(self, df):
        # Calculate moving averages
        df['SMA20'] = df['close'].rolling(window=20).mean()
        df['short_ma'] = df['close'].rolling(window=50).mean()
        df['long_ma'] = df['close'].rolling(window=200).mean()

        df.loc[df['short_ma'] > df['long_ma'], 'trend'] = 1
        df.loc[df['short_ma'] < df['long_ma'], 'trend'] = 0

        rsi_indicator = RSIIndicator(close=df['close'])
        df['RSI'] = rsi_indicator.rsi()
        average_true_range = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        )
        df['ATR'] = average_true_range.average_true_range()

        return df

    def trade_conditions(self, df, i, portfolio):
        atr = df.loc[i, 'ATR']
        close = df.loc[i, 'close']
        ma = df.loc[i, 'SMA20']
        spread = df.loc[i, 'spread'] 

        prev_close = df.loc[i - 1, 'close'] if i > 0 else None
        prev_ma = df.loc[i - 1, 'SMA20'] if i > 0 else None

        # スプレッドを通貨単位に変換
        spread_cost = spread * 0.01 * self.lot_size  # 0.2銭なら20円

        # 利確と損切りの閾値
        TAKE_PROFIT = atr * 1
        STOP_LOSS = atr * -1

        if portfolio['position'] == 'long':
            profit = (close - portfolio['entry_price']) - spread_cost
            if profit > TAKE_PROFIT or profit < STOP_LOSS:
                return 'exit_long'
        elif prev_close is not None and prev_ma is not None \
            and prev_close < prev_ma and close > ma:
            return 'entry_long'
        else:
            return None


