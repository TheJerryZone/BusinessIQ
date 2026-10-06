"""Shared logic: cleaning, SQLite schema/helpers and the order simulator."""
import os
import sqlite3
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import config

TIME_FMT = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog (
    sku_id                    INTEGER PRIMARY KEY,
    item_identifier           TEXT,
    item_type                 TEXT,
    item_fat_content          TEXT,
    item_weight               REAL,
    item_visibility           REAL,
    rating                    REAL,
    base_price                REAL,
    outlet_identifier         TEXT,
    outlet_type               TEXT,
    outlet_size               TEXT,
    outlet_location_type      TEXT,
    outlet_establishment_year INTEGER
);
CREATE TABLE IF NOT EXISTS orders (
    order_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    order_time   TEXT    NOT NULL,
    sku_id       INTEGER NOT NULL REFERENCES catalog(sku_id),
    quantity     INTEGER NOT NULL,
    unit_price   REAL    NOT NULL,
    sales_amount REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_time ON orders(order_time);
DROP VIEW IF EXISTS v_orders;
CREATE VIEW v_orders AS
SELECT o.order_id, o.order_time, o.quantity, o.unit_price, o.sales_amount,
       c.sku_id, c.item_identifier, c.item_type, c.item_fat_content,
       c.item_visibility, c.rating, c.outlet_identifier, c.outlet_type,
       c.outlet_size, c.outlet_location_type
FROM orders o JOIN catalog c USING (sku_id);
"""

# ----------------------------------------------------------------- cleaning
def clean_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw Excel data WITHOUT throwing rows away."""
    df = raw.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.drop_duplicates()

    # Item type: Title Case, keeping "and" lower-case
    df["item_type"] = (df["item_type"].str.strip().str.title()
                       .str.replace(" And ", " and ", regex=False))

    # Fat content: LF / low fat / reg / Regular ... -> 3 clean labels.
    # Ids starting with "NC" are non-consumables (household etc.), so fat
    # content does not apply to them.
    fat = df["item_fat_content"].str.strip().str.lower().map(
        {"lf": "Low Fat", "low fat": "Low Fat", "reg": "Regular", "regular": "Regular"})
    df["item_fat_content"] = fat.where(~df["item_identifier"].str.startswith("NC"), "Non-Edible")

    df["outlet_location_type"] = df["outlet_location_type"].str.strip().str.title()

    # Missing weight: fill from the same item elsewhere, else overall median.
    # (The old notebook dropna()'d these rows, which deleted whole outlets.)
    df["item_weight"] = (df["item_weight"]
                         .fillna(df.groupby("item_identifier")["item_weight"].transform("mean"))
                         .fillna(df["item_weight"].median()))

    # Visibility of exactly 0 is impossible for an item on a shelf.
    vis = df["item_visibility"].where(df["item_visibility"] > 0)
    df["item_visibility"] = (vis.fillna(vis.groupby(df["item_identifier"]).transform("mean"))
                             .fillna(vis.median()))

    if df["outlet_size"].isna().any():
        mode = df.groupby("outlet_type")["outlet_size"].transform(
            lambda s: s.mode().iat[0] if s.notna().any() else "Medium")
        df["outlet_size"] = df["outlet_size"].fillna(mode)

    df = df.dropna(subset=["sales"]).reset_index(drop=True)
    df.insert(0, "sku_id", np.arange(1, len(df) + 1))
    return df


def to_catalog(clean: pd.DataFrame) -> pd.DataFrame:
    cat = clean.rename(columns={"sales": "base_price"})
    return cat[["sku_id", "item_identifier", "item_type", "item_fat_content", "item_weight",
                "item_visibility", "rating", "base_price", "outlet_identifier", "outlet_type",
                "outlet_size", "outlet_location_type", "outlet_establishment_year"]]

# ----------------------------------------------------------------- database
def connect(write: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.execute("PRAGMA busy_timeout = 15000")
    if write:
        conn.execute("PRAGMA journal_mode = WAL")   # lets the dashboard read while the feed writes
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def read_sql(sql: str, params=()) -> pd.DataFrame:
    conn = connect()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def load_catalog() -> pd.DataFrame:
    return read_sql("SELECT * FROM catalog")


def load_orders(start: datetime, end: datetime) -> pd.DataFrame:
    df = read_sql("SELECT * FROM v_orders WHERE order_time >= ? AND order_time <= ?",
                  (start.strftime(TIME_FMT), end.strftime(TIME_FMT)))
    df["order_time"] = pd.to_datetime(df["order_time"])
    return df


def last_order_time():
    v = read_sql("SELECT MAX(order_time) AS t FROM orders")["t"].iat[0]
    return pd.to_datetime(v).to_pydatetime() if v else None


def insert_orders(conn: sqlite3.Connection, orders: pd.DataFrame) -> None:
    conn.executemany(
        "INSERT INTO orders (order_time, sku_id, quantity, unit_price, sales_amount) VALUES (?,?,?,?,?)",
        orders[["order_time", "sku_id", "quantity", "unit_price", "sales_amount"]]
        .itertuples(index=False, name=None))
    conn.commit()

# ---------------------------------------------------------------- simulator
_HOUR = np.array([.15, .10, .08, .08, .10, .20, .45, .80, 1.1, 1.3, 1.5, 1.8,
                  1.9, 1.6, 1.3, 1.3, 1.5, 1.9, 2.1, 1.9, 1.4, .9, .5, .25])
_HOUR = _HOUR / _HOUR.mean()                       # lunch + evening peaks, quiet nights
_OUTLET_WEIGHT = {"Supermarket Type3": 1.6, "Supermarket Type1": 1.0,
                  "Supermarket Type2": 0.8, "Grocery Store": 0.4}


def intensity(ts: pd.DatetimeIndex) -> np.ndarray:
    """Relative traffic (average 1.0) for each timestamp: time of day + weekend bump."""
    weekday = np.where(ts.dayofweek >= 5, 1.125, 0.95)
    return _HOUR[ts.hour] * weekday


class Simulator:
    """Generates realistic orders that reference real catalog rows."""

    def __init__(self, catalog: pd.DataFrame, seed=None):
        self.rng = np.random.default_rng(seed)
        self.sku = catalog["sku_id"].to_numpy()
        self.price = catalog["base_price"].to_numpy()
        w = (catalog["item_visibility"].to_numpy() + 0.02) * \
            catalog["outlet_type"].map(_OUTLET_WEIGHT).fillna(1.0).to_numpy()
        self.p = w / w.sum()

    def make_orders(self, times) -> pd.DataFrame:
        times = pd.DatetimeIndex(times)
        n = len(times)
        idx = self.rng.choice(len(self.sku), size=n, p=self.p)
        qty = self.rng.choice([1, 2, 3, 4, 5], size=n, p=[.55, .25, .12, .05, .03])
        unit = np.round(self.price[idx] * self.rng.uniform(0.9, 1.1, n), 2)
        return pd.DataFrame({"order_time": times.strftime(TIME_FMT), "sku_id": self.sku[idx],
                             "quantity": qty, "unit_price": unit,
                             "sales_amount": np.round(unit * qty, 2)})

    def history_times(self, start: datetime, end: datetime, per_minute: float) -> pd.DatetimeIndex:
        minutes = pd.date_range(pd.Timestamp(start).floor("min"), end, freq="min")
        counts = self.rng.poisson(per_minute * intensity(minutes))
        base = np.repeat(minutes.values, counts)
        t = base + self.rng.integers(0, 60_000, len(base)).astype("timedelta64[ms]")
        t = np.sort(t)
        t = t[(t >= np.datetime64(start)) & (t <= np.datetime64(end))]
        return pd.DatetimeIndex(t)

    def live_count(self, now: datetime, per_minute: float, seconds: float) -> int:
        lam = per_minute / 60 * seconds * intensity(pd.DatetimeIndex([now]))[0]
        return int(self.rng.poisson(lam))


def backfill(conn, sim: Simulator, per_minute: float, days: int = None) -> int:
    """Fill the gap between the newest order (or `days` ago) and now."""
    days = days or config.HISTORY_DAYS
    now = datetime.now().replace(microsecond=0)
    floor = now - timedelta(days=days)
    last = conn.execute("SELECT MAX(order_time) FROM orders").fetchone()[0]
    start = max(floor, datetime.strptime(last, TIME_FMT) + timedelta(seconds=1)) if last else floor
    if start >= now:
        return 0
    orders = sim.make_orders(sim.history_times(start, now, per_minute))
    for i in range(0, len(orders), 50_000):
        insert_orders(conn, orders.iloc[i:i + 50_000])
    return len(orders)


# ------------------------------------------------- build + live loop (reusable)
def build_database(days=None, rate=None, seed=None, log=print) -> int:
    """raw xlsx -> clean -> catalog table -> simulated order history."""
    days = days or config.HISTORY_DAYS
    rate = rate or config.ORDERS_PER_MINUTE
    raw = pd.read_excel(config.RAW_XLSX)
    clean = clean_raw(raw)
    log(f"Raw rows: {len(raw):,}  ->  clean rows: {len(clean):,}  (nothing dropped)")
    log(f"Outlets kept: {clean['outlet_identifier'].nunique()} of {raw['Outlet Identifier'].nunique()}")
    log("Fat content: " + str(clean["item_fat_content"].value_counts().to_dict()))
    try:                                            # handy for Power BI / Excel
        export = clean.drop(columns="sku_id")
        export.columns = [c.replace("_", " ").title() for c in export.columns]
        export.to_excel(config.CLEAN_XLSX, index=False)
    except OSError:
        pass                                        # read-only host: not essential

    config.DB_PATH.parent.mkdir(exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        p = str(config.DB_PATH) + suffix
        if os.path.exists(p):
            os.remove(p)
    conn = connect(write=True)
    conn.executescript(SCHEMA)
    catalog = to_catalog(clean)
    catalog.to_sql("catalog", conn, if_exists="append", index=False)
    n = backfill(conn, Simulator(catalog, seed=seed), rate, days)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    log(f"Created {config.DB_PATH.name}: {len(catalog):,} catalog rows, {n:,} orders over {days} days")
    return n


def feed_loop(rate=None, speed=1.0, tick=1.0, stop=None, log=None) -> int:
    """Insert live orders until `stop` (threading.Event) is set. Returns orders added."""
    rate = rate or config.ORDERS_PER_MINUTE
    conn = connect(write=True)
    total = 0
    try:
        sim = Simulator(pd.read_sql_query("SELECT * FROM catalog", conn))
        filled = backfill(conn, sim, rate)          # catch up if the feed was off
        if log and filled:
            log(f"Caught up: added {filled:,} orders for the time the feed was off")
        while not (stop is not None and stop.is_set()):
            t0 = time.time()
            now = datetime.now().replace(microsecond=0)
            n = sim.live_count(now, rate * speed, tick)
            if n:
                insert_orders(conn, sim.make_orders([now] * n))
                total += n
                if log:
                    log(f"{now:%H:%M:%S}  +{n} order(s)   total this session: {total}")
            time.sleep(max(0.0, tick - (time.time() - t0)))
    finally:
        conn.close()
    return total
