import sys
from datetime import datetime


def _log(step: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [search_products] [{step}] {message}"
    try:
        print(line, flush=True)
    except (UnicodeEncodeError, AttributeError, OSError):
        # Fallback: encode to ASCII with replacement for incompatible stdout
        # (e.g., Windows cp1252 terminal or sys.stdout=None in daemon threads)
        try:
            safe = line.encode("ascii", errors="replace").decode("ascii")
            print(safe, flush=True)
        except Exception:
            try:
                print(safe, file=sys.stderr)
            except Exception:
                pass
