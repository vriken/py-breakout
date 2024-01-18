from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utility import implement_strategy, asyncio, pd
import ast
import argparse
from datetime import datetime, timedelta
from visualize import visualize_stock
from utility import get_historical_data

# Define the amount to invest
amount_to_invest = 200

current_date = datetime.now()
start_date = current_date - timedelta(days = 40)
start_date_str = start_date.strftime('%Y-%m-%d')
end_date = current_date - timedelta(days=1)
end_date_str = end_date.strftime('%Y-%m-%d')

async def process_ticker(ticker, lower_length, upper_length):
    try:
        stock = await get_historical_data(ticker, start_date_str, end_date_str, "1d")
        # Apply Donchian channels and drop rows with NaN values in relevant columns
        stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
        stock = stock.dropna()
        # Implement strategy and format actions
        actions, _, earning = implement_strategy(stock, amount_to_invest)
        return [{'Ticker': ticker, 'Date': action['Date'], 'Action': action['Action'], 'Shares': action['Shares'], 'Price': action['Price'], 'Volume': action['Volume'], 'Earning': earning} for action in actions]
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return []

# Main asynchronous function
async def main():
    best_tickers_df = pd.read_csv('./input/best_tickers.csv')

    parser = argparse.ArgumentParser()
    parser.add_argument("--visualize", action="store_true", help="Visualize the stock data")
    args = parser.parse_args()  # This line creates the 'args' variable

    results = []
    plots = []
    for _, row in best_tickers_df.iterrows():
        ticker = row['ticker']
        lower_length = round(row['lower_length'], 2)
        upper_length = round(row['upper_length'], 2)
        actions = await process_ticker(ticker, lower_length, upper_length)
        results.extend(actions)

        # Visualization part
        if args.visualize:
            stock = await get_historical_data(ticker, start_date_str, end_date_str, "1d")
            stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
            stock = stock.dropna()
            plot = visualize_stock(stock, actions)
            plots.append(plot)

    # Show all the plots at the end if visualization is enabled
    if args.visualize:
        for plot in plots:
            plot.show()

    results_df = pd.DataFrame(results)
    results_df.to_csv('output/output_file.csv', index=False)

if __name__ == "__main__":
    asyncio.run(main())
