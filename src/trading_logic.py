from datetime import datetime, timedelta
from math import floor
from random import randint
from avanza import OrderType
import os
from simulator import SimulatedAccountManager

class TradingLogic:
    def __init__(self, avanza, account_manager):
        self.avanza = avanza
        self.account_manager = account_manager
        self.highest_prices = {}
        self.lowest_prices = {}

    def calculate_brokerage_fee(self, transaction_amount):
        fee = transaction_amount * 0.0025  # 0.25%
        return max(fee, 1)  # Minimum fee is 1 SEK

    def calculate_donchian_channels(self, historical_data_dict, donchian_parameters):
        for orderbook_id, data_list in historical_data_dict.items():
            upper_length = int(donchian_parameters[orderbook_id]['upper_length'])
            lower_length = int(donchian_parameters[orderbook_id]['lower_length'])

            if len(data_list) >= max(upper_length, lower_length):
                recent_high_data = data_list[-upper_length:]
                self.highest_prices[orderbook_id] = max(data['high'] for data in recent_high_data)

                recent_low_data = data_list[-lower_length:]
                self.lowest_prices[orderbook_id] = min(data['low'] for data in recent_low_data)

    async def process_realtime_data(self, orderbook_id, stock_data):
        try:
            orderbook_id = int(orderbook_id)
            buy_ask = float(stock_data['buyPrice'])
            sell_ask = float(stock_data['sellPrice'])
            datetime_obj = stock_data['updatedTime']

            if isinstance(datetime_obj, str):
                datetime_obj = datetime.strptime(datetime_obj, "%Y-%m-%d %H:%M:%S")

            if isinstance(datetime_obj, int):
                datetime_obj = datetime.fromtimestamp(datetime_obj / 1000)  # Convert milliseconds to seconds

            if datetime_obj and datetime_obj <= (datetime.now() - timedelta(seconds=5)):
                return
            
            highest_price = round(self.highest_prices.get(orderbook_id, 0), 3)
            lowest_price = round(self.lowest_prices.get(orderbook_id, 0), 3)

            owned_stocks = self.account_manager.get_owned_stocks({})
            # if not owned_stocks:
            #     print("Error: owned_stocks is empty or None")
            #     return

            owned_stocks = {int(k): v for k, v in owned_stocks.items()}
            budget = self.account_manager.get_balance()

            # Exit strategy
            if buy_ask < lowest_price:
                if orderbook_id in owned_stocks and owned_stocks[orderbook_id]['shares'] > 0:
                    print(f'Checking sell conditions for {orderbook_id}: current buy ask is {buy_ask}, lowest price is {lowest_price}')
                    sell_shares = owned_stocks[orderbook_id]['shares']
                    transaction_amount = sell_shares * buy_ask - self.calculate_brokerage_fee(sell_shares * buy_ask)
                    budget += transaction_amount

                    owned_stocks[orderbook_id]['shares'] = 0
                    current_date = datetime.now().date()
                    if isinstance(self.account_manager, SimulatedAccountManager):
                        self.account_manager.update_balance(transaction_amount)
                        self.account_manager.update_owned_stocks(orderbook_id, -sell_shares, buy_ask)
                    else: 
                        await self.avanza.place_order(
                            account_id=os.getenv('AVANZA_ACCOUNT_ID'),
                            order_book_id=orderbook_id,
                            order_type=OrderType.SELL,
                            price=buy_ask,
                            valid_until=current_date,
                            volume=sell_shares
                        )
                        print(f"SOLD {sell_shares} shares of {orderbook_id} at {buy_ask}.")

            # Entry strategy
            else:
                if orderbook_id not in owned_stocks or owned_stocks[orderbook_id]['shares'] == 0:
                    print(f"Entering buy logic for {orderbook_id}")
                    max_budget_for_stock = budget
                    max_affordable_shares = floor(max_budget_for_stock / sell_ask)
                    stock_purchase_impact = (sell_ask + self.calculate_brokerage_fee(sell_ask)) * max_affordable_shares

                    if max_affordable_shares > 0:
                        shares_to_buy = max_affordable_shares if stock_purchase_impact < budget * 0.2 else randint(1, max_affordable_shares)
                        if shares_to_buy >= 1 and sell_ask > highest_price:
                            transaction_amount = shares_to_buy * sell_ask + self.calculate_brokerage_fee(shares_to_buy * sell_ask)
                            if transaction_amount <= budget and transaction_amount > 250:
                                budget -= transaction_amount
                                owned_stocks[orderbook_id] = {'price': sell_ask, 'shares': shares_to_buy}
                                current_date = datetime.now()
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
                                print(f"Insufficient budget or transaction amount too low for {orderbook_id}.")
                        else:
                            print(f"Not buying any shares of {orderbook_id} as calculated shares to buy is less than one.")
                    else:
                        print(f"Not buying any shares of {orderbook_id} as max_affordable_shares is zero.")
        except Exception as e:
            print(f"Error processing realtime data for orderbook ID {orderbook_id}: {e}")

# Example usage:
# trading_logic = TradingLogic(avanza, account_manager)