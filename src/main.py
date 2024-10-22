import pandas as pd
from BWAFPO import np
from datetime import datetime, timedelta
from avanza import Avanza, ChannelType
from yahoo_fin.stock_info import get_data
from dotenv import load_dotenv
import backoff
import asyncio
import nest_asyncio
from os import path, getenv
from websockets.exceptions import ConnectionClosedError
from account_manager import AccountManager
from trading_logic import TradingLogic
from simulator import SimulatedAccountManager
from BWAFPO import BlackWidowOptimization
import argparse

base_path = path.dirname(path.dirname(path.realpath(__file__)))
stocks = pd.read_csv(f'{base_path}/input/best_tickers.csv')
whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

parser = argparse.ArgumentParser()
parser.add_argument('--sim', action='store_true', help='Run in simulation mode')
args = parser.parse_args()

def calculate_expected_returns_and_covariance(historical_data_dict):
    # Convert historical data to returns
    returns = {}
    for id, data in historical_data_dict.items():
        prices = [d['close'] for d in data]
        returns[id] = np.diff(np.log(prices))

    # Calculate expected returns and covariance matrix
    expected_returns = {id: np.mean(ret) for id, ret in returns.items()}
    cov_matrix = np.cov(list(returns.values()))

    return expected_returns, cov_matrix

def optimize_portfolio(historical_data_dict):
    expected_returns, cov_matrix = calculate_expected_returns_and_covariance(historical_data_dict)
    
    num_assets = len(historical_data_dict)
    bwo = BlackWidowOptimization(num_spiders=1, num_iterations=100, expected_returns=expected_returns, cov_matrix=cov_matrix, num_assets=num_assets)
    
    optimal_weights, optimal_fitness = bwo.optimize()
    
    return dict(zip(historical_data_dict.keys(), optimal_weights))

def integrate_account_manager(avanza):
    if args.sim:
        print("Running in simulation mode")
        account_manager = SimulatedAccountManager()
    else:
        print("Running in live mode")
        account_manager = AccountManager(avanza)
    
    # Get the account balance
    balance = account_manager.get_balance()
    print(f"Current balance: {balance}")

    # Get owned stocks
    owned_stocks = account_manager.get_owned_stocks()
    print("Owned Stocks:")
    for stock_id, stock_info in owned_stocks.items():
        print(f"ID: {stock_id}, Info: {stock_info}")

    return account_manager, owned_stocks  # Return both account_manager and owned_stocks

current_date = datetime.now()
start_date = (current_date - timedelta(days=3)).strftime('%Y-%m-%d')
end_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')

@backoff.on_exception(backoff.expo, Exception, max_tries=5)
def initialize_avanza():
    load_dotenv()
    return Avanza({
        'username': getenv('AVANZA_USERNAME'),
        'password': getenv('AVANZA_PASSWORD'),
        'totpSecret': getenv('AVANZA_TOTP_SECRET')
    })

class WebSocketSubscription:
    def __init__(self, avanza, whitelisted_tickers, trading_logic):
        self.avanza = avanza
        self.whitelisted_tickers = whitelisted_tickers
        self.trading_logic = trading_logic

    async def subscribe_to_channels(self):
        for id in self.whitelisted_tickers.values():
            await self.resilient_subscribe(id)

    @backoff.on_exception(backoff.expo, ConnectionClosedError, max_tries=5)
    async def resilient_subscribe(self, id):
        try:
            await self.avanza.subscribe_to_id(ChannelType.QUOTES, str(id), self.callback)
        except ConnectionClosedError as e:
            print(f"WebSocket connection closed unexpectedly for ID {id}: {e}. Reconnecting...")
            raise
        except Exception as e:
            print(f"Error subscribing to channel for ID {id}: {e}")

    async def callback(self, data):
        try:
            orderbook_id = int(data['data']['orderbookId'])
            print(data)
            stock_data = {
                'buyPrice': data['data']['buyPrice'],
                'sellPrice': data['data']['sellPrice'],
                'updatedTime': data['data']['updatedTime']
            }
            await self.trading_logic.process_realtime_data(orderbook_id, stock_data)
        except Exception as e:
            print(f"Error in callback: {e}")

nest_asyncio.apply()

async def run_websocket_subscription():
    avanza = initialize_avanza()
    
    # Integrate account manager
    account_manager, owned_stocks = integrate_account_manager(avanza)

    print('Fetching historical data for whitelisted stocks from Yahoo')
    historical_data_dict = {}
    for _, row in stocks.iterrows():
        try:
            historical_data = get_data(row['ticker'], start_date, end_date, "1d")
            historical_data_dict[int(row['id'])] = [{
                'high': r['high'],
                'low': r['low'],
                'index': i.strftime("%Y-%m-%d")
            } for i, r in historical_data.iterrows()]
        except Exception as e:
            print(f"Error fetching data for orderbook ID {row['id']}: {e}")

    optimal_portfolio = optimize_portfolio(historical_data_dict)
    print("Optimal portfolio weights:", optimal_portfolio)

    # Update your trading logic to use these weights
    trading_logic.set_portfolio_weights(optimal_portfolio)
    
    # Initialize TradingLogic
    trading_logic = TradingLogic(avanza, account_manager)
    
    # Calculate Donchian channels
    donchian_parameters = {id: {'upper_length': 40, 'lower_length': 30} for id in whitelisted_tickers.values()}
    trading_logic.calculate_indicators(historical_data_dict, donchian_parameters)
    
    websocket_subscription = WebSocketSubscription(avanza, whitelisted_tickers, trading_logic)
    await websocket_subscription.subscribe_to_channels()

asyncio.ensure_future(run_websocket_subscription())
asyncio.get_event_loop().run_forever()