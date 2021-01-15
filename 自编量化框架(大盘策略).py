import tushare as ts
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time

class AstockTrading(): # 策略类
    def __init__(self, stratege_name, Start_date, End_date, origin_total_value):
        self._token = '' # 改成自己的token
        self._pro = ts.pro_api(self._token)
        day = self._pro.trade_cal(exchange='', start_date=Start_date, 
                                  end_date=End_date)
        self._current_buy = [] # 当天买入
        self._current_sell = [] # 当天卖出
        self._hands_list = [] # 当天买入手数
        self.start_date = Start_date
        self.end_date = End_date
        self._datum_target = '399300.SZ' # 基准标的，沪深300
        self._stratege_name = stratege_name
        self._origin_total_value = origin_total_value # 持仓总市值
        self._total_value = self._origin_total_value # 持仓初始市值
        ########## 主要属性 ↓
        self._daily_tick = pd.DataFrame([]) # 初始化每日行情，在get_tick函数里面赋值
        self._history_order = [] # 历史指令
        self._calendar = day[day['is_open'] == 1].cal_date.apply(str)
        # ↑ 交易日历,一次性赋值,列表,字符串
        self._buy_list = [] # 每日买入股票列表
        self._trade_number = 0 # 交易日期序号
        self._history_value = [] # 历史市值
        self._hold_stock = {} # 目前持仓股票
        self._connot_sell_stock = [] # 跌停股，不能卖
        self._stata = pd.DataFrame([]) # 最后用于统计
    
    def get_tick(self): # 获取行情
        daily_tick = self._pro.daily(
            trade_date=self._calendar.iloc[self._trade_number]) # 原始每日行情数据
        self._daily_tick = daily_tick.sort_values('amount', ascending=False, 
                                                  inplace = False) # 按成交额排序

    def order_target_value(self, stock, target_value): # 交易函数,设置手续费也是在这里
        # stock 是代码
        # target_value 是目标份额
        # 这里结算总市值self._total_value
        target_value = int(target_value)
        df = self._daily_tick # 为了便于书写，self._daily_tick赋值为当日行情数据df
        if target_value == 0:
            # 卖出后，新市值加等于新价格减与成本的差乘以手数再乘以100
            self._total_value += ((df[df.ts_code==stock]['close'] - \
                self._hold_stock[stock][1])*\
                    self._hold_stock[stock][0]) * 100
            self._total_value = float(self._total_value)
            self._current_sell.append(stock)
        else: # 买入
            hands = target_value / df[df.ts_code==stock]['close'].iloc[0] \
                // 100 - 1
            self._hands_list.append(hands)
            # ↑可买手数
            cost = hands * 100 * df[df.ts_code==stock]['close'].iloc[0] * 0.0015
            if cost < 5: # 手续费不低于5元
                cost = 5
            self._total_value -= cost
            # 买入就是总权益减去手续费
            self._current_buy.append(stock)
            self._total_value = float(self._total_value)

    def before_market_open(self): # 盘前函数
        self._connot_sell_stock = []
        df2 = self._pro.suspend_d(suspend_type='S', \
            trade_date=self._calendar.iloc[self._trade_number]).ts_code
        self.get_tick() # 模拟交易前获取每日行情，相当于预先知道行情了，都是以收盘价交易
        limit_down_list = self._pro.limit_list(
            trade_date=self._calendar.iloc[self._trade_number],
            limit_type='D').ts_code # 当天跌停股票
        for stock in self._hold_stock: # 统计持仓里面哪些是跌停的
            if stock in list(limit_down_list) or stock in list(df2):
                self._connot_sell_stock.append(stock) # 持仓里面的跌停或停牌股列表
 
    def after_market_close(self): # 盘后函数
        self._trade_number += 1 # 今日行情获取完毕之后，序号加1，下次获取下一日行情数据

    def strategy(self): # 策略重点修改这里
        # 选股策略是选出每日成交量最大的10个股票，特殊情况顺延
        df = self._daily_tick
        # ↑为了便于书写，self._daily_tick赋值为当日行情数据df
        self._buy_list = [] # 重新初始化买入列表
        for index in list(df.index):
            last_pchg = df.loc[index]['pct_chg']
            code = df.loc[index]['ts_code']
            if -3 <= last_pchg  <= 3:
                self._buy_list.append(code)
            if len(self._buy_list) == 10 - len(self._connot_sell_stock):
                break # 选到10支退出,排除跌停股，因此可能少于10个

    def trade(self):# 选股结束，开始交易
        df = self._daily_tick
        MonPerStock = self._total_value / len(self._buy_list)
        for stock in self._hold_stock: # stock 应当是代码字符串
            if stock not in self._buy_list and stock not in self._connot_sell_stock:
                # 如果已经持有的股票不在买入列表也没跌停或停牌，卖出
                self.order_target_value(stock, 0) # 目标卖空
                self._history_order.append(['{}, {}, {}手, 现价{}元, 卖空'.format(
                    df[df.ts_code==stock]['trade_date'].iloc[0],
                    stock,
                    'all',
                    float(df[df.ts_code==stock]['close'].iloc[0]))]) # 增加记录
        for stock in self._buy_list: # stock 应当是代码字符串
            self.order_target_value(stock, MonPerStock) # 目标买入
            self._history_order.append(['{}, {}, {}手 现价{}元, 买入'.format(
                    df[df.ts_code==stock]['trade_date'].iloc[0],
                    stock,
                    int(MonPerStock//float(df[df.ts_code==stock]['close'])//100),
                    float(df[df.ts_code==stock]['close'].iloc[0]))]) # 增加记录
        self.update_hold() # 更新持仓和市值
        self.after_market_close() # 盘后，日期加一

    def update_hold(self): # 更新持仓和市值
        df = self._daily_tick
        for num in range(len(self._current_sell)):
            del self._hold_stock[self._current_sell[num]]
        for num in range(len(self._current_buy)):
            self._hold_stock[self._current_buy[num]] = \
                [int(self._hands_list[num]),
                 float(df[df.ts_code==self._current_buy[num]]['close'])]
        self._current_buy = [] # 当天买入
        self._current_sell = [] # 当天卖出
        self._hands_list = [] # 当天买入手数
        self._history_value.append(self._total_value) # 记录历史市值

    def picture_all(self, base_rate, my_rate, new_calendar): # 交易结束,作图和结算
        print('最终市值{}元，收益率{:.3f}%'.format(self._total_value, 
                                      (self._total_value - \
                                       self._origin_total_value)/\
                                          self._origin_total_value*100))
        self._stata['历史市值'] = my_rate
        self._stata['沪深300'] = base_rate
        base_rate = pd.DataFrame(base_rate)
        my_rate = pd.DataFrame(my_rate)
        self._stata['超额收益'] = my_rate - base_rate
        plt.plot(new_calendar, self._stata)
        plt.legend(['历史市值', '沪深300', '超额收益'])
        plt.xlabel('日期',fontsize='15')
        plt.ylabel('收益率',fontsize='15')
        plt.title('{}策略'.format(self._stratege_name),fontsize=15)
        plt.grid()
        plt.show()

    def stata(self): # 统计结果
        # 把历史市值改成pd.Series形式
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
        new_calendar = pd.DataFrame([])
        new_calendar['trade_date'] = [datetime.strptime(day, '%Y%m%d').date()\
                                        for day in self._calendar]
        hs300 = self._pro.index_daily(ts_code=self._datum_target, 
                                start_date=self.start_date, 
                                end_date=self.end_date)
        base_rate = [] # 基准收益率
        hs300_close = list(hs300['close'][::-1]) # 沪深300收盘价
        for i in range(len(hs300_close)):
            base_rate.append((hs300_close[i] - hs300_close[0])/hs300_close[0])
        # ↑ 沪深300累计收益率
        my_rate = [] # 策略收益率
        for i in range(len(self._history_value)):
            my_rate.append((self._history_value[i] - \
                            self._origin_total_value)/self._origin_total_value)
        return base_rate, my_rate, new_calendar

def count_day(start_date, end_date): # 计算交易日期数
    token = '' # 改成自己的token    
    pro = ts.pro_api(token)
    day = pro.trade_cal(exchange='', start_date=start_date, 
                                  end_date=end_date)
    calendar = day[day['is_open'] == 1].cal_date.apply(str)
    return len(calendar)

def main(start_date, end_date, origin_value): # 主函数
    mys = AstockTrading('amount_strategy', start_date, end_date, origin_value)
    days = count_day(start_date, end_date) # 计算日期间隔
    for i in range(days): # 循环若干交易日
        time.sleep(0.05)
        mys.before_market_open()
        mys.strategy()
        mys.trade()
        if i%10 == 0:
            print('>> 第{}天执行完毕'.format(i+1)) # 通报进度
    base_rate, my_rate, new_calendar = mys.stata()
    mys.picture_all(base_rate, my_rate, new_calendar) # 统计作图
    return mys._history_order # 交易记录

if __name__ == '__main__':
    logger = main('20170101', '20170531', 100000) # 交易起止日期，本金，logger是交易记录，程序中途会弹出可视化交易情况图，需要自己手动保存