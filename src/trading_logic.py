from datetime import datetime, timedelta
from math import floor
from random import randint
from avanza import OrderType
import os
from simulator import SimulatedAccountManager
from BWAFPO import calculate_moving_average, calculate_slope, calculate_rsi

class TradingLogic:
    def __init__(self, avanza, account_manager):
        self.avanza = avanza
        self.account_manager = account_manager
        self.highest_prices = {}
        self.lowest_prices = {}
        self.portfolio_weights = {}
        self.ma_slopes = {}
        self.rsi_values = {}

    def calculate_indicators(self, historical_data_dict, donchian_parameters):
        for orderbook_id, data_list in historical_data_dict.items():
            upper_length = int(donchian_parameters[orderbook_id]['upper_length'])
            lower_length = int(donchian_parameters[orderbook_id]['lower_length'])

            if len(data_list) >= max(upper_length, lower_length, 30, 14):  # Ensure we have enough data
                prices = [data['close'] for data in data_list]
                
                # Calculate Donchian channels
                recent_high_data = data_list[-upper_length:]
                self.highest_prices[orderbook_id] = max(data['high'] for data in recent_high_data)
                recent_low_data = data_list[-lower_length:]
                self.lowest_prices[orderbook_id] = min(data['low'] for data in recent_low_data)

                # Calculate 30-day MA slope
                ma_30 = calculate_moving_average(prices, 30)
                self.ma_slopes[orderbook_id] = calculate_slope(ma_30)

                # Calculate 14-day RSI
                self.rsi_values[orderbook_id] = calculate_rsi(prices, 14)[-1]

    def set_portfolio_weights(self, weights):
        self.portfolio_weights = weights

    def calculate_brokerage_fee(self, transaction_amount):
        fee = transaction_amount * 0.0025  # 0.25%
        return max(fee, 1)  # Minimum fee is 1 SEK

    def calculate_current_weight(self, orderbook_id):
        owned_stocks = self.account_manager.get_owned_stocks({})
        total_portfolio_value = self.account_manager.get_balance()
        for stock_id, stock_data in owned_stocks.items():
            total_portfolio_value += stock_data['price'] * stock_data['shares']
        
        if orderbook_id in owned_stocks:
            stock_value = owned_stocks[orderbook_id]['price'] * owned_stocks[orderbook_id]['shares']
            return stock_value / total_portfolio_value if total_portfolio_value > 0 else 0
        return 0

    def calculate_shares_to_buy(self, orderbook_id, target_weight, current_weight, buy_ask):
        total_value = self.account_manager.get_balance()
        for stock_id, stock_data in self.account_manager.get_owned_stocks({}).items():
            total_value += stock_data['price'] * stock_data['shares']
        
        target_value = total_value * target_weight
        current_value = total_value * current_weight
        value_to_buy = target_value - current_value
        
        return floor(value_to_buy / buy_ask) if buy_ask > 0 else 0

    def calculate_shares_to_sell(self, orderbook_id, target_weight, current_weight, sell_ask):
        total_value = self.account_manager.get_balance()
        for stock_id, stock_data in self.account_manager.get_owned_stocks({}).items():
            total_value += stock_data['price'] * stock_data['shares']
        
        target_value = total_value * target_weight
        current_value = total_value * current_weight
        value_to_sell = current_value - target_value
        
        return floor(value_to_sell / sell_ask) if sell_ask > 0 else 0


    async def process_realtime_data(self, orderbook_id, stock_data):
        try:
            orderbook_id = int(orderbook_id)
            buy_ask = float(stock_data['buyPrice'])
            sell_ask = float(stock_data['sellPrice'])
            datetime_obj = datetime.strptime(stock_data['updatedTime'], "%Y-%m-%d %H:%M:%S")

            if isinstance(datetime_obj, str):
                datetime_obj = datetime.strptime(datetime_obj, "%Y-%m-%d %H:%M:%S")

            if datetime_obj and datetime_obj <= (datetime.now() - timedelta(seconds=5)):
                return

            highest_price = round(self.highest_prices.get(orderbook_id, 0), 3)
            lowest_price = round(self.lowest_prices.get(orderbook_id, 0), 3)
            ma_slope = self.ma_slopes.get(orderbook_id, 0)
            rsi = self.rsi_values.get(orderbook_id, 50)

            owned_stocks = self.account_manager.get_owned_stocks({})
            if not owned_stocks:
                print("Error: owned_stocks is empty or None")
                return

            owned_stocks = {int(k): v for k, v in owned_stocks.items()}

            target_weight = self.portfolio_weights.get(orderbook_id, 0)
            current_weight = self.calculate_current_weight(orderbook_id)

            if current_weight < target_weight:
                shares_to_buy = self.calculate_shares_to_buy(orderbook_id, target_weight, current_weight, buy_ask)
                if shares_to_buy > 0 and sell_ask > highest_price and ma_slope > 0 and rsi < 30:
                    transaction_amount = shares_to_buy * sell_ask + self.calculate_brokerage_fee(shares_to_buy * sell_ask)
                    if transaction_amount <= self.account_manager.get_balance():
                        current_date = datetime.now().date()
                        if isinstance(self.account_manager, SimulatedAccountManager):
                            self.account_manager.update_balance(-transaction_amount)
                            self.account_manager.update_owned_stocks(orderbook_id, shares_to_buy, sell_ask)
                        else:
                            await self.avanza.place_order(
                                account_id=os.getenv('AVANZA_ACCOUNT_ID'),
                                order_book_id=orderbook_id,
                                order_type=OrderType.BUY,
                                price=sell_ask,
                                valid_until=current_date,
                                volume=shares_to_buy
                            )
                        print(f"BUY {shares_to_buy} shares of {orderbook_id} at {sell_ask}.")
                    else:
                        print(f"Insufficient balance to buy {shares_to_buy} shares of {orderbook_id}.")
                else:
                    print(f"Not buying any shares of {orderbook_id}. Conditions not met.")

            elif current_weight > target_weight:
                shares_to_sell = self.calculate_shares_to_sell(orderbook_id, target_weight, current_weight, sell_ask)
                if shares_to_sell > 0 and buy_ask < lowest_price and ma_slope < 0 and rsi > 70:
                    if orderbook_id in owned_stocks and owned_stocks[orderbook_id]['shares'] >= shares_to_sell:
                        transaction_amount = shares_to_sell * buy_ask - self.calculate_brokerage_fee(shares_to_sell * buy_ask)
                        current_date = datetime.now().date()
                        if isinstance(self.account_manager, SimulatedAccountManager):
                            self.account_manager.update_balance(transaction_amount)
                            self.account_manager.update_owned_stocks(orderbook_id, -shares_to_sell, buy_ask)
                        else: 
                            await self.avanza.place_order(
                                account_id=os.getenv('AVANZA_ACCOUNT_ID'),
                                order_book_id=orderbook_id,
                                order_type=OrderType.SELL,
                                price=buy_ask,
                                valid_until=current_date,
                                volume=shares_to_sell
                            )
                        print(f"SOLD {shares_to_sell} shares of {orderbook_id} at {buy_ask}.")
                    else:
                        print(f"Not enough shares to sell {shares_to_sell} of {orderbook_id}.")
                else:
                    print(f"Not selling any shares of {orderbook_id}. Conditions not met.")
            else:
                print(f"Current weight is equal to target weight for {orderbook_id}. Not buying or selling.")
        
        except Exception as e:
            print(f"Error processing realtime data for orderbook ID {orderbook_id}: {e}")

