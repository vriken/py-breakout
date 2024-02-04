from utility import pd, datetime, timedelta, get_historical_data_sync, implement_strategy, BayesianOptimization, extract_ids_and_update_csv, load_dotenv, Avanza, getenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load ticker data from a CSV file
ticker_df = pd.read_csv('./input/best_tickers.csv')
ticker_list = ticker_df[['id', 'ticker']].to_dict('records')


# Define the parameter space
pbounds = {
    'lower_length': (1, 40),
    'upper_length': (2, 50)
}

def objective_for_ticker(ticker, lower_length, upper_length):
    try:
        print(f"Processing {ticker}")
        current_date = datetime.now()
        start_date = current_date - timedelta(days = 52)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date = current_date - timedelta(days=0)
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        stock = get_historical_data_sync(ticker, start_date_str, end_date_str, "1d")
        stock.index.name = 'date'
        stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
        stock = stock.dropna()
        stock.index = pd.to_datetime(stock.index)
        
        _, _, earning = implement_strategy(stock, 1000, lower_length, upper_length)
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

        optimizer.maximize(init_points=10, n_iter=50)
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
result_df = pd.DataFrame(results, columns=['id', 'ticker', 'target', 'lower_length', 'upper_length'])
result_df.to_csv('./output/optimized_tickers_with_id.csv', index=False)
