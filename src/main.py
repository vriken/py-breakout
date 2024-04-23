import threading
import logging
import asyncio
from utility import initialize_avanza
import avanza_api
import trade
import realtime

# Configure logging
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Avanza only once
avanza = initialize_avanza()

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

def run_script(name, avanza=None):
    """Run a script with optional Avanza object, ensuring an event loop for asyncio operations."""
    script_info = scripts[name]
    module = script_info['module']
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        if script_info['needs_avanza'] and avanza:
            coroutine = module.main(avanza)
        else:
            coroutine = module.main()
        loop.run_until_complete(coroutine)
    except Exception as e:
        logging.error(f"{name} encountered an error: {e}")
        # Optionally handle restart logic here, but consider implications on Avanza object
    finally:
        loop.close()

def start_script_in_thread(name):
    """Start a script in a separate thread, passing Avanza if needed."""
    thread = threading.Thread(target=run_script, args=(name, avanza if scripts[name]['needs_avanza'] else None))
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
