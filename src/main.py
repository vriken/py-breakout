import threading
import logging
import asyncio
from utility import initialize_avanza
import avanza_api
import trade
import realtime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Script configuration
scripts = {
    'avanza_api': {
        'module': avanza_api,
        'needs_avanza': True
    },
    'trade': {
        'module': trade,
        'needs_avanza': True
    },
    'realtime': {
        'module': realtime,
        'needs_avanza': False
    }
}

def run_script(name, avanza):
    """Run a script with Avanza object, handling re-authentication on 401/402 errors."""
    script_info = scripts[name]
    module = script_info['module']
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:  # Continuously try to run the script unless a critical error occurs
        try:
            coroutine = module.main(avanza)
            loop.run_until_complete(coroutine)
            break  # Exit loop if coroutine completes successfully
        except Exception as e:
            if '401' in str(e) or '402' in str(e):
                logging.error(f"Authentication error encountered: {e}. Re-authenticating...")
                avanza = initialize_avanza()  # Reinitialize the Avanza object
            else:
                logging.error(f"{name} encountered a critical error: {e}")
                break  # Exit loop if a non-authentication related error occurs
        finally:
            loop.close()

def start_script_in_thread(name):
    """Start a script in a separate thread, ensuring it has the necessary Avanza object."""
    avanza = initialize_avanza() if scripts[name]['needs_avanza'] else None
    thread = threading.Thread(target=run_script, args=(name, avanza))
    scripts[name]['thread'] = thread
    thread.start()
    return thread

def main():
    """Start all scripts defined in the configuration."""
    threads = [start_script_in_thread(name) for name in scripts]
    for thread in threads:
        thread.join()  # Keep this if you want the main script to wait for all threads

if __name__ == "__main__":
    main()
