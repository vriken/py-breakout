from utility import *

ticker_df = pd.read_csv('stock_data/formatted_stock_tickers.csv', header = None)
ticker_list = ticker_df[0].tolist()

# Path to the output file
output_file = 'output/realtime_parameters.csv'

# Clear the existing file if it exists
if os.path.isfile(output_file):
    os.remove(output_file)

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

def optimize_and_write_for_ticker(ticker):
    try:
        optimizer = BayesianOptimization(
            f=lambda lower_length, upper_length: objective_for_ticker(ticker, lower_length, upper_length),
            pbounds=pbounds,
            random_state=1,
            allow_duplicate_points=True
        )

        optimizer.maximize(init_points=32, n_iter=48)   
        
        # Write this ticker's best parameters to CSV
        result_data = optimizer.max['params']
        result_data['target'] = optimizer.max['target']
        result = pd.DataFrame([result_data], index=[ticker])
        
        if not os.path.isfile('output/realtime_parameters.csv'):
            result.to_csv('output/realtime_parameters.csv', header=True)
        else: # else it exists so append without writing the header
            result.to_csv('output/realtime_parameters.csv', mode='a', header=False)

    except Exception as e:                              
        print(f"Error optimizing {ticker}: {e}")

# Process each ticker in parallel and write results
with ThreadPoolExecutor(max_workers=15) as executor:
    executor.map(optimize_and_write_for_ticker, ticker_list)
