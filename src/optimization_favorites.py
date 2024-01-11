from utility import datetime, timedelta, get_historical_data_sync, implement_strategy, BayesianOptimization

ticker_list = ['TRANS.ST', 'SYSR.ST', 'SANION.ST', 'CNCJO-B.ST','INDT.ST', 'INSTAL.ST', 'KDEV.ST', 'K2A-B.ST', 'NETI-B.ST', 'NIBE-B.ST']
# ticker_df = pd.read_csv('stock_data/formatted_stock_tickers.csv', header = None)
# ticker_list = ticker_df[0].tolist()

all_actions = []
# Define the parameter space
pbounds = {
    'lower_length': (1, 45),
    'upper_length': (5, 55)
}

def objective_for_ticker(ticker, lower_length, upper_length):
    try:
        print(f"Processing {ticker}")
        current_date = datetime.now()
        start_date = current_date - timedelta(weeks=52*2)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = current_date.strftime('%Y-%m-%d')
        
        stock = get_historical_data_sync(ticker, start_date_str, end_date_str, "1d")
        stock.index.name = 'date'
        stock[['dcl', 'dcm', 'dcu']] = stock.ta.donchian(lower_length=lower_length, upper_length=upper_length)
        stock = stock.dropna()
        stock.index = pd.to_datetime(stock.index)
        
        actions, final_equity, earning = implement_strategy(stock, 1000, lower_length, upper_length)
        return earning

    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return 0

from concurrent.futures import ThreadPoolExecutor, as_completed

def optimize_for_ticker(ticker):
    try:
        optimizer = BayesianOptimization(
            f=lambda lower_length, upper_length: objective_for_ticker(ticker, lower_length, upper_length),
            pbounds=pbounds,
            random_state=1,
            allow_duplicate_points=True
        )

        optimizer.maximize(init_points=32, n_iter=48)   
        return ticker, optimizer.max                    
    except Exception as e:                              
        print(f"Error optimizing {ticker}: {e}")
        return ticker, None
    
best_parameters_per_ticker = {}

with ThreadPoolExecutor(max_workers=15) as executor:
    futures = {executor.submit(optimize_for_ticker, ticker): ticker for ticker in ticker_list}
    for future in as_completed(futures):
        ticker, result = future.result()
        if result is not None:
            best_parameters_per_ticker[ticker] = result

pd.DataFrame(best_parameters_per_ticker).transpose().to_csv('input/best_whitelisted.csv', index=True)
