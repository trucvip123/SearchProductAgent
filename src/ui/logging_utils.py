"""Logging utilities for Streamlit UI."""

import os
import sys
from datetime import datetime


LOG_FILE = os.path.join(os.path.dirname(__file__), "../../streamlit_app.log")


def print_log(msg: str):
    """Write to log file and console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}\n"
    
    # Write directly to file
    try:
        with open(LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:
            f.write(log_msg)
            f.flush()
    except Exception as e:
        pass
    
    # Try stderr
    try:
        sys.stderr.write(log_msg)
        sys.stderr.flush()
    except Exception:
        pass
