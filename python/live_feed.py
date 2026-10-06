"""OPTIONAL stand-alone live feed. The dashboard already runs its own feed, so you only
need this to drive extra traffic, e.g.  python live_feed.py --speed 10   (demo mode)."""
import argparse

import config
import core

ap = argparse.ArgumentParser()
ap.add_argument("--rate", type=float, default=config.ORDERS_PER_MINUTE, help="avg orders per minute")
ap.add_argument("--speed", type=float, default=1.0, help="rate multiplier")
ap.add_argument("--tick", type=float, default=1.0, help="seconds between checks")
a = ap.parse_args()

if not config.DB_PATH.exists():
    raise SystemExit("Database not found - run build_database.py (or start the dashboard) first.")
print(f"Live feed running (~{a.rate * a.speed:g} orders/min). Press Ctrl+C to stop.")
try:
    core.feed_loop(a.rate, a.speed, a.tick, log=print)
except KeyboardInterrupt:
    print("\nStopped.")
