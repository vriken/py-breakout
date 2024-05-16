import asyncio
import threading
import logging
from utility import initialize_avanza
import avanza_api
import trade
import realtime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

scripts = {
    'avanza_api': {'module': avanza_api, 'needs_avanza': True},
    'trade': {'module': trade, 'needs_avanza': True},
    'realtime': {'module': realtime, 'needs_avanza': True}
}

def run_script(name, avanza):
    script_info = scripts[name]
    module = script_info['module']
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        coroutine = module.main(avanza)
        loop.run_until_complete(coroutine)
    except Exception as e:
        if '401' in str(e) or '402' in str(e):  # Session expired
            logging.error(f"Session expired: {e}. Re-authenticating...")
            avanza = initialize_avanza()  # Reinitialize if needed
            return run_script(name, avanza)  # Recursive call with new session
        else:
            logging.error(f"{name} encountered a critical error: {e}")
            return
    finally:
        loop.close()

def start_script_in_thread(name, avanza):
    """Start a script in a separate thread, ensuring it has the necessary Avanza object."""
    thread = threading.Thread(target=run_script, args=(name, avanza))
    scripts[name]['thread'] = thread
    thread.start()
    return thread

def main():
    """Start all scripts defined in the configuration."""
    avanza = initialize_avanza()
    threads = [start_script_in_thread(name, avanza) for name in scripts if scripts[name]['needs_avanza']]
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
