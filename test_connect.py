import MetaTrader5 as mt5

# MT5に接続
if not mt5.initialize():
    print("MT5の初期化に失敗しました")
    mt5.shutdown()
    quit()

# 接続が成功した場合、情報を表示
print("MT5に接続しました")
print(mt5.terminal_info())
