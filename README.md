基于Tushare数据库，具体调用什么接口，根据实际情况而定。

# whole_Market_strategy：大盘策略

修改token与strategy部分即可，该大盘策略框架中已经写好了一个策略模板，即买入每日成交量最大的10支股票，写好token之后理论上可直接运行。

该策略的问题是不能计算前复权行情，用的都是不复权行情。

# Solo_Stock_strategy：个股策略

修改token与strategy部分即可，完善策略函数后可以运行。

这里调用的是前复权数据。

# 设计思路

```

AstockTrading()         交易框架（类）
|- __init__()           初始化属性
|- get_tick()           获得行情数据
|- order_target_value() 将标的交易到指定仓位
|- before_market_open() 盘前初始化
|- after_market_close() 盘后函数
|- strategy()           策略函数
|- trade()              交易函数
|- update_hold()        更新持仓函数
|- picture_all()        作图函数
|- statistics()         统计函数
|- count_day()          用来计算起止日期中间有多少交易日，以此确定循环次数
|- run()                运行整个交易

```