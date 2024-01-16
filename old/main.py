from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utility import implement_strategy, asyncio, pd
import ast
import argparse
from datetime import datetime, timedelta
from visualize import visualize_stock

# Define the whitelisted tickers
whitelisted_tickers = {'TRANS.ST' :  564938, 'SYSR.ST' : 97407, 'SANION.ST' : 475457, 'CNCJO-B.ST' : 5279, 'INDT.ST' : 26607, 'INSTAL.ST' : 752039, 'KDEV.ST' : 285632, 'K2A-B.ST' : 971402, 'NETI-B.ST' : 5440, 'NIBE-B.ST' : 5325}

amount_to_invest = 200

current_date = datetime.now()
start_date = current_date - timedelta(weeks=52*2)
start_date_str = start_date.strftime('%Y-%m-%d')
end_date_str = current_date.strftime('%Y-%m-%d')

async def process_ticker(ticker, params):
    try:
        lower_length = round(params['lower_length'], 2)
        upper_length = round(params['upper_length'], 2)

        stock = await get_historical_data(ticker, start_date_str, end_date_str, "1d")

        # Apply Donchian channels and drop rows with NaN values in relevant columns
        stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
        stock = stock.dropna()

        # Implement strategy and format actions
        actions, final_equity, earning = implement_strategy(stock, amount_to_invest)
        return [{'Ticker': ticker, 'Date': action['Date'], 'Action': action['Action'], 'Shares': action['Shares'], 'Price': action['Price'], 'Volume': action['Volume'], 'Earning': earning} for action in actions]

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return []

# Main asynchronous function
async def main():
    best_tickers_df = pd.read_csv('/Users/ake/Documents/probable_spoon/input/best_tickers.csv')
    best_tickers_df = best_tickers_df[best_tickers_df['ticker'].isin(whitelisted_tickers)]

    parser = argparse.ArgumentParser()
    parser.add_argument("--visualize", action="store_true", help="Visualize the stock data")
    args = parser.parse_args()  # This line creates the 'args' variable

    results = []
    for _, row in best_tickers_df.iterrows():
        ticker = row['ticker']
        params = eval(row['params'])
        actions = await process_ticker(ticker, params)
        results.extend(actions)

    if args.visualize:
        plots = []
        for _, row in best_tickers_df.iterrows():
            ticker = row['ticker']
            params = eval(row['params'])

            # Define lower_length and upper_length here
            lower_length = round(params['lower_length'], 2)
            upper_length = round(params['upper_length'], 2)

            stock = await get_historical_data(ticker, start_date_str, end_date_str, "1d")
            stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
            stock = stock.dropna()

            # Process the ticker to get actions
            actions = await process_ticker(ticker, params)
            plot = visualize_stock(stock, actions)
            plots.append(plot)

        # Show all the plots at the end
        for plot in plots:
            plot.show()

    results_df = pd.DataFrame(results)
    results_df.to_csv('output/output_file.csv', index=False)

if __name__ == "__main__":
    asyncio.run(main())