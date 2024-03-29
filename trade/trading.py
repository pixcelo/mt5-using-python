import sys
sys.path.append('d:\\dev\\mt5-python')

from modules import TradingStrategy
import MetaTrader5 as mt5

class Trading:
    def __init__(self, lot_size=0.01, slippage=3, params=None):
        self.symbol = params['symbol']
        self.lot_size = lot_size
        self.slippage = slippage
        self.strategy = TradingStrategy(params=params)
        self.magic_number = 19850001

        self.portfolio = {
            'position': None,  # "long" or "short"
            'entry_price': None,
            'entry_point': 0,
            'trailing_stop': 0,
            'take_profit': None,
            'stop_loss': None,
            'profit': 0
        }

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
                "magic": self.magic_number,
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
    
    # Initialize portfolio state
    def init_portfolio(self):
        return {
            'position': None,  # "long" or "short"
            'entry_price': None,
            'entry_point': 0,
            'trailing_stop': 0,
            'take_profit': None,
            'stop_loss': None,
            'profit': 0
        }
    
    def trade_conditions(self, df, i, portfolio):
        closes = df['close'].values
        spreads = df['spread'].values
        return self.strategy.trade_logic_trend_reversal(df, i, portfolio, closes, spreads)