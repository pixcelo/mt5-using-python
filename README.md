# mt5-python

## Install
```
pip freeze > requirements.txt
```

## Login
`settings.ini`に定義
```
[DEFAULT]
mt5_path = C:/Program Files/MT5/terminal64.exe
mt5_login = 123456
mt5_password = password
mt5_server = MetaQuotes-Demo
```

## Spread
- 取引数量 × pips ＝ コスト
- 1万通貨・1.5pips(0.015円)の場合
- 1万通貨 × 0.015pips ＝ 150円

OANDAのスプレッドの単位は「銭」or「pips」
https://www.oanda.jp/course/spread

## Lot


## Reference
- [python_metatrader5](https://www.mql5.com/ja/docs/python_metatrader5)