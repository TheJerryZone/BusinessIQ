"""Rebuild everything from the raw Excel file.     python build_database.py"""
import argparse

import config
import core

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=config.HISTORY_DAYS, help="days of history to generate")
ap.add_argument("--rate", type=float, default=config.ORDERS_PER_MINUTE, help="avg orders per minute")
ap.add_argument("--seed", type=int, default=None)
a = ap.parse_args()
core.build_database(a.days, a.rate, a.seed)
