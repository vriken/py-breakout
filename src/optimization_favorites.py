from utility import read_csv, DataFrame, to_datetime, datetime, timedelta, get_data, implement_strategy, BayesianOptimization, extract_ids_and_update_csv, load_dotenv, Avanza, getenv, ta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load ticker data from a CSV file
ticker_df = read_csv('/Users/ake/Documents/probable_spoon_a/input/best_tickers.csv')
ticker_list = ticker_df[['id', 'ticker']].to_dict('records')


# Define the parameter space
pbounds = {
    'lower_length': (1, 10),
    'upper_length': (11, 30)
}

def objective_for_ticker(ticker, lower_length, upper_length):
    try:
        print(f"Processing {ticker}")
        current_date = datetime.now()
        start_date = current_date - timedelta(weeks = 52)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date = current_date - timedelta(days=1)
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        stock = get_data(ticker, start_date_str, end_date_str, "1d").copy()
        stock['date'] = stock.index
        stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
        stock = stock.dropna()
        #stock['date'] = to_datetime(stock['date'])
        #print(stock)
        
        _, _, earning = implement_strategy(stock, 4000, lower_length, upper_length)
        return earning

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return 0

def optimize_for_ticker(ticker_record):
    ticker_id = ticker_record['id']
    ticker = ticker_record['ticker']
    try:
        optimizer = BayesianOptimization(
            f=lambda lower_length, upper_length: objective_for_ticker(ticker, lower_length, upper_length),
            pbounds=pbounds,
            random_state=1,
            allow_duplicate_points=True
        )

        optimizer.maximize(init_points=10, n_iter=40)
        max_params = optimizer.max
        max_params['id'] = ticker_id  # Add the ticker_id to the result
        return max_params

    except Exception as e:
        print(f"Error optimizing {ticker}: {e}")
        return None

results = []

# Process each ticker in parallel and collect results
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(optimize_for_ticker, ticker_record): ticker_record for ticker_record in ticker_list}
    for future in as_completed(futures):
        params = future.result()
        if params is not None:
            ticker_record = futures[future]
            results.append([ticker_record['id'], ticker_record['ticker'], params['target'], params['params']['lower_length'], params['params']['upper_length']])

# Save results to a CSV file
result_df = DataFrame(results, columns=['id', 'ticker', 'target', 'lower_length', 'upper_length'])
result_df.to_csv('/Users/ake/Documents/probable_spoon_a/output/optimized_tickers_with_id.csv', index=False)
