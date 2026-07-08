"""Async/threading utilities for Streamlit."""

import asyncio
import threading
import concurrent.futures


def run_async(coro):
    """
    Run async coroutine properly in Streamlit context.
    Handles the event loop lifecycle correctly to avoid "Event loop is closed" errors.
    """
    try:
        loop = asyncio.get_running_loop()
        # If there's already a running loop (Streamlit case), run in executor
        future = concurrent.futures.Future()
        
        def run_in_new_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result = new_loop.run_until_complete(coro)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                new_loop.close()
        
        thread = threading.Thread(target=run_in_new_loop, daemon=True)
        thread.start()
        thread.join()
        return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(coro)
