"""BusinessIQ - real-time business analytics.      streamlit run dashboard.py
Dark control-room layout. Reads orders from SQLite and refreshes itself while the feed runs."""
import threading
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import core

CUR = config.CURRENCY
st.set_page_config(page_title="BusinessIQ | Real-Time Business Analytics", page_icon="📈", layout="wide")


@st.cache_resource(show_spinner="First start: building the database (about 10 seconds)...")
def start_backend():
    """Runs once per server process: builds the DB if missing, then starts the live order
    feed in a background thread, so no second terminal / process is needed."""
    if not config.DB_PATH.exists():
        core.build_database(log=lambda m: None)
    else:
        last = core.last_order_time()
        if last and (datetime.now() - last).total_seconds() < 15:
            return "external"                 # a separate live_feed.py is already writing
    t = threading.Thread(target=core.feed_loop, daemon=True, name="businessiq-feed")
    t.start()
    return t


start_backend()

# ------------------------------------------------------------------ design tokens
BG, PANEL, EDGE = "#0F1217", "#1B1D21", "#2B2E34"
TEXT, MUTED, GRID = "#E6E6E6", "#8B8F98", "#2A2D33"
AMBER, ORANGE, RED, GREEN, LIME = "#F2B632", "#FF7A1A", "#E5342B", "#2FBF8F", "#7ED957"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500&family=Barlow+Condensed:wght@500;600;700&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Barlow', sans-serif; }}
.stApp {{ background: radial-gradient(1200px 600px at 50% -10%, #1b2029 0%, {BG} 60%); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: #14171c; border-right: 1px solid {EDGE}; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }}
div[class*="st-key-panel"] {{
    background: linear-gradient(180deg, #202328 0%, {PANEL} 100%);
    border: 1px solid {EDGE}; border-radius: 4px; padding: 14px 18px 12px 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,.45);
}}
.hdr {{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 14px; }}
.hdr h1 {{ font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:2rem; letter-spacing:.04em;
          margin:0; padding:0; color:{TEXT}; line-height:1.1; }}
.hdr h1 span {{ color:{AMBER}; }}
.hdr p {{ margin:2px 0 0 0; color:{MUTED}; font-size:.85rem; }}
.pill {{ font-family:'Barlow Condensed',sans-serif; font-size:.95rem; letter-spacing:.05em; padding:4px 12px;
         border:1px solid {EDGE}; border-radius:3px; background:#15181d; color:{TEXT}; white-space:nowrap; }}
.pill i {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:8px; }}
.ptitle {{ font-family:'Barlow Condensed',sans-serif; font-weight:600; font-size:1.05rem; letter-spacing:.06em;
           color:{TEXT}; margin:0 0 6px 0; padding-bottom:6px; border-bottom:1px solid {EDGE}; }}
.ptitle small {{ float:right; color:{MUTED}; font-family:'Barlow',sans-serif; font-weight:400; letter-spacing:0; font-size:.75rem; }}
.kgrid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:8px; }}
.kcard {{ background:#17191d; border:1px solid {GRID}; border-radius:3px; padding:12px 14px; position:relative; overflow:hidden; }}
.kcard:before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--c); }}
.kcard .l {{ color:{MUTED}; font-size:.78rem; }}
.kcard .v {{ font-family:'Barlow Condensed',sans-serif; font-weight:600; font-size:1.95rem; color:{TEXT}; line-height:1.15; white-space:nowrap; }}
.kcard .d {{ font-size:.8rem; display:flex; justify-content:space-between; gap:8px; }}
.kcard .d em {{ font-style:normal; color:{MUTED}; }}
.up {{ color:{GREEN}; }} .down {{ color:{RED}; }} .flat {{ color:{MUTED}; }}
.tbl .row {{ display:grid; gap:8px; align-items:center; font-size:.82rem; padding:8px 10px; margin-bottom:5px;
             background:#17191d; border:1px solid {GRID}; border-radius:3px; position:relative; }}
.tbl .head {{ background:transparent; border:none; color:{MUTED}; font-size:.72rem; padding:0 10px 2px; }}
.tbl .row span {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:{TEXT}; }}
.tbl .head span {{ color:{MUTED}; }}
.tbl .m {{ color:{MUTED} !important; }}
.tbl .r {{ text-align:right; }}
.tbl .n {{ font-family:'Barlow Condensed',sans-serif; font-weight:600; font-size:.95rem; }}
.tbl .bar {{ position:absolute; left:0; bottom:0; height:2px; background:linear-gradient(90deg,{AMBER},{ORANGE}); }}
.note {{ color:{MUTED}; font-size:.72rem; margin-top:4px; }}
@media (max-width: 900px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} }}
.note {{ color:{MUTED}; font-size:.72rem; margin-top:2px; }}
@media (max-width: 900px) {{ .kgrid {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# label -> (window length, chart bucket size)
WINDOWS = {
    "Last 15 minutes": (timedelta(minutes=15), "1min"),
    "Last hour": (timedelta(hours=1), "5min"),
    "Last 24 hours": (timedelta(hours=24), "1h"),
    "Last 7 days": (timedelta(days=7), "6h"),
    "Last 14 days": (timedelta(days=14), "12h"),
}


@st.cache_data(ttl=300)
def catalog_options():
    cat = core.load_catalog()
    return (sorted(cat["item_type"].unique()), sorted(cat["outlet_location_type"].unique()),
            sorted(cat["outlet_type"].unique()))


def compact(v: float) -> str:
    """12,345,678 -> 12.35M so big numbers fit the KPI strip."""
    for lim, suf in ((1e9, "B"), (1e6, "M"), (1e4, "K")):
        if abs(v) >= lim:
            return f"{v / lim:.2f}{suf}"
    return f"{v:,.0f}"


def pct(cur, prev):
    """(text, css class) for the change vs the previous window."""
    if not prev:
        return "no earlier data", "flat"
    d = (cur - prev) / prev * 100
    return f"{d:+.1f}%", ("up" if d >= 0 else "down")


def ago(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h {s % 3600 // 60}m ago"
    return f"{s // 86400}d ago"


# ------------------------------------------------------------------ sidebar
all_types, all_tiers, all_outlets = catalog_options()
st.sidebar.title("BusinessIQ Controls")
window_label = st.sidebar.selectbox("Time window", list(WINDOWS), index=2)
categories = st.sidebar.multiselect("Item category", all_types, default=all_types)
tiers = st.sidebar.multiselect("Location tier", all_tiers, default=all_tiers)
outlet_types = st.sidebar.multiselect("Outlet type", all_outlets, default=all_outlets)
st.sidebar.divider()
auto_refresh = st.sidebar.toggle("Auto-refresh", value=True)
refresh_s = st.sidebar.select_slider("Refresh every (seconds)", [2, 5, 10, 30], value=5,
                                     disabled=not auto_refresh)


# ------------------------------------------------------------------ helpers
def money(v, d=0):
    return f"{CUR}{v:,.{d}f}"


def base_layout(fig, height):
    fig.update_layout(
        height=height, margin=dict(t=6, b=6, l=6, r=6), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Barlow, sans-serif", color=MUTED, size=11),
        hovermode="x unified", hoverlabel=dict(bgcolor="#14171c", bordercolor=EDGE, font=dict(color=TEXT)),
        legend=dict(orientation="h", y=1.13, x=0, bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(showgrid=False, linecolor=EDGE, tickfont=dict(size=10), zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(size=10), linecolor="rgba(0,0,0,0)",
                     automargin=True)
    return fig


def buckets(df, start, now, freq):
    s = (df.set_index("order_time")
         .resample(freq).agg(revenue=("sales_amount", "sum"), orders=("order_id", "count")))
    return s.reindex(pd.date_range(pd.Timestamp(start).floor(freq), pd.Timestamp(now).floor(freq),
                                   freq=freq), fill_value=0)


def trend_chart(s, ps):
    """Revenue (orange area) + orders (red line, right axis) + previous period (grey)."""
    fig = go.Figure()
    if ps is not None:
        fig.add_trace(go.Scatter(x=s.index, y=ps["revenue"], mode="lines", name="Previous period",
                                 line=dict(color="rgba(230,230,230,.45)", width=1, shape="spline"),
                                 hovertemplate=CUR + "%{y:,.0f}"))
    fig.add_trace(go.Scatter(
        x=s.index, y=s["revenue"], mode="lines", name="Revenue", yaxis="y",
        line=dict(color=ORANGE, width=2, shape="spline"), hovertemplate=CUR + "%{y:,.0f}",
        fill="tozeroy", fillgradient=dict(type="vertical", colorscale=[[0, "rgba(255,122,26,0)"],
                                                                         [1, "rgba(255,122,26,.8)"]])))
    fig.add_trace(go.Scatter(x=s.index, y=s["orders"], mode="lines+markers", name="Orders", yaxis="y2",
                             line=dict(color=RED, width=2, shape="spline"),
                             marker=dict(size=5, color=AMBER), hovertemplate="%{y:,} orders"))
    fig = base_layout(fig, 330)
    fig.update_layout(yaxis=dict(tickprefix=CUR, tickformat="~s", rangemode="tozero"),
                      yaxis2=dict(overlaying="y", side="right", showgrid=False, tickformat=",d", rangemode="tozero",
                                  tickfont=dict(size=10, color=RED), automargin=True))
    return fig


PIE_COLORS = [AMBER, ORANGE, RED, GREEN, LIME, "#5B8DEF", "#5A5F69"]
CFG = {"displayModeBar": False}


def donut_chart(labels, values, centre_big, centre_small, height=330):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=.64, sort=False, direction="clockwise",
        marker=dict(colors=PIE_COLORS[:len(labels)], line=dict(color=PANEL, width=2)),
        textinfo="percent", textfont=dict(size=11, color="#111"), insidetextorientation="horizontal",
        hovertemplate="%{label}<br>" + CUR + "%{value:,.0f} (%{percent})<extra></extra>"))
    fig.add_annotation(text=f"<span style='font-size:22px;color:{TEXT}'><b>{centre_big}</b></span>"
                            f"<br><span style='font-size:11px;color:{MUTED}'>{centre_small}</span>",
                       x=.5, y=.5, showarrow=False)
    fig.update_layout(height=height, margin=dict(t=6, b=6, l=6, r=6), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Barlow, sans-serif", color=MUTED, size=11),
                      legend=dict(orientation="h", y=-0.05, x=.5, xanchor="center", bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor="#14171c", bordercolor=EDGE, font=dict(color=TEXT)))
    return fig


def outlet_bars(o):
    o = o.sort_values("revenue")
    fig = go.Figure(go.Bar(
        x=o["revenue"], y=o["outlet_identifier"], orientation="h", text=[money(v) for v in o["revenue"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=TEXT, size=11),
        marker=dict(color=o["revenue"], colorscale=[[0, "#8A4B12"], [1, AMBER]], line=dict(width=0)),
        hovertemplate="%{y}<br>" + CUR + "%{x:,.0f}<extra></extra>"))
    fig = base_layout(fig, 310)
    fig.update_layout(hovermode="closest", margin=dict(t=6, b=6, l=6, r=70))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, tickprefix=CUR, tickformat="~s")
    fig.update_yaxes(showgrid=False)
    return fig


def hour_bars(cur):
    h = cur["order_time"].dt.hour.value_counts().reindex(range(24), fill_value=0).sort_index()
    colors = [RED if v == h.max() and v > 0 else ORANGE for v in h]
    fig = go.Figure(go.Bar(x=h.index, y=h.values, marker=dict(color=colors, line=dict(width=0)),
                           hovertemplate="%{x}:00 - %{x}:59<br>%{y:,} orders<extra></extra>"))
    fig = base_layout(fig, 310)
    fig.update_layout(hovermode="closest", bargap=.25)
    fig.update_xaxes(tickmode="array", tickvals=list(range(0, 24, 3)),
                     ticktext=[f"{x:02d}:00" for x in range(0, 24, 3)])
    return fig


def price_bubbles(g):
    mx = g["revenue"].max() or 1
    top = set(g.nlargest(5, "revenue").index)
    fig = go.Figure(go.Scatter(
        x=g["units"], y=g["price"], mode="markers+text", text=[i if i in top else "" for i in g.index],
        textposition="top center", textfont=dict(color=TEXT, size=10),
        marker=dict(size=12 + 34 * g["revenue"] / mx, color=g["revenue"],
                    colorscale=[[0, RED], [.5, ORANGE], [1, AMBER]], opacity=.85,
                    line=dict(color=AMBER, width=1)),
        customdata=list(zip(g.index, g["revenue"])),
        hovertemplate="%{customdata[0]}<br>Units %{x:,}<br>Unit price " + CUR + "%{y:,.2f}<br>Revenue "
                      + CUR + "%{customdata[1]:,.0f}<extra></extra>"))
    fig = base_layout(fig, 310)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(showgrid=True, gridcolor=GRID, title_text="Units sold", title_font=dict(size=10))
    fig.update_yaxes(tickprefix=CUR, title_text="Avg unit price", title_font=dict(size=10))
    return fig


def panel_title(text, right=""):
    st.markdown(f"<div class='ptitle'>{text}<small>{right}</small></div>", unsafe_allow_html=True)


def kpi(label, value, delta, prev_text, color):
    txt, cls = delta
    return (f"<div class='kcard' style='--c:{color}'><div class='l'>{label}</div><div class='v'>{value}</div>"
            f"<div class='d'><span class='{cls}'>{txt}</span><em>{prev_text}</em></div></div>")


def table(headers, widths, rows, aligns, bars=None):
    """headers/rows are lists of strings; aligns 'l' | 'r' | 'm' (muted); bars = 0-100 per row."""
    def cell(v, a, head=False):
        cls = {"l": "", "r": "r n", "m": "m"}[a]
        if head and a == "r":
            cls = "r"
        return f"<span class='{cls}'>{v}</span>"
    h = "".join(cell(x, a, True) for x, a in zip(headers, aligns))
    out = f"<div class='tbl'><div class='row head' style='grid-template-columns:{widths}'>{h}</div>"
    for i, r in enumerate(rows):
        bar = f"<div class='bar' style='width:{bars[i]:.0f}%'></div>" if bars else ""
        out += (f"<div class='row' style='grid-template-columns:{widths}'>"
                + "".join(cell(x, a) for x, a in zip(r, aligns)) + bar + "</div>")
    return out + "</div>"


# --------------------------------------------------------------- live view
run_every = f"{refresh_s}s" if auto_refresh else None


@st.fragment(run_every=run_every)
def live_view():
    now = datetime.now().replace(microsecond=0)
    span, freq = WINDOWS[window_label]
    start = now - span

    # ---- header + live status
    last = core.last_order_time()
    lag = (now - last).total_seconds() if last else None
    if lag is not None and lag < 90:
        pill = f"<span class='pill'><i style='background:{GREEN};box-shadow:0 0 8px {GREEN}'></i>Live · last order {ago(lag)}</span>"
    else:
        pill = (f"<span class='pill'><i style='background:{RED}'></i>Feed offline"
                + (f" · last order {ago(lag)}" if lag is not None else "") + "</span>")
    st.markdown(f"<div class='hdr'><div><h1>Business<span>IQ</span></h1>"
                f"<p>Real-time business analytics · {window_label.lower()} · updated {now:%H:%M:%S}"
                + (f" · every {refresh_s}s" if auto_refresh else " · auto-refresh off")
                + f"</p></div>{pill}</div>", unsafe_allow_html=True)

    if not (categories and tiers and outlet_types):
        st.info("Select at least one option in each sidebar filter.")
        return

    # ---- data: current window + previous window of equal length (for deltas)
    df = core.load_orders(now - 2 * span, now)
    df = df[df["item_type"].isin(categories) & df["outlet_location_type"].isin(tiers)
            & df["outlet_type"].isin(outlet_types)]
    cur, prev = df[df["order_time"] >= start], df[df["order_time"] < start]
    if cur.empty:
        st.info("No orders in this window for the selected filters yet.")
        return

    mins = span.total_seconds() / 60
    rev, n, units = cur["sales_amount"].sum(), len(cur), int(cur["quantity"].sum())
    p_rev, p_n, p_units = prev["sales_amount"].sum(), len(prev), int(prev["quantity"].sum())
    aov, p_aov = rev / n, (p_rev / p_n if p_n else 0)
    uprice, p_uprice = rev / units, (p_rev / p_units if p_units else 0)
    rate, p_rate = n / mins, p_n / mins
    big = cur.loc[cur["sales_amount"].idxmax()]
    p_big = prev["sales_amount"].max() if p_n else 0
    n_out = cur["outlet_identifier"].nunique()
    rpo, p_rpo = rev / n_out, (p_rev / prev["outlet_identifier"].nunique() if p_n else 0)
    pv = lambda v, f: ("prev " + f(v)) if p_n else "no earlier data"

    # ================= KPIs: every figure with its previous-period value
    with st.container(key="panel_kpis"):
        panel_title("Key figures", f"change vs the previous {window_label.lower().replace('last ', '')}")
        st.markdown("<div class='kgrid'>"
                    + kpi("Revenue", money(rev), pct(rev, p_rev), pv(p_rev, money), AMBER)
                    + kpi("Orders", f"{n:,}", pct(n, p_n), pv(p_n, lambda v: f"{v:,}"), ORANGE)
                    + kpi("Units sold", f"{units:,}", pct(units, p_units), pv(p_units, lambda v: f"{v:,}"), RED)
                    + kpi("Avg order value", money(aov, 2), pct(aov, p_aov), pv(p_aov, lambda v: money(v, 2)), GREEN)
                    + kpi("Avg unit price", money(uprice, 2), pct(uprice, p_uprice), pv(p_uprice, lambda v: money(v, 2)), AMBER)
                    + kpi("Orders per minute", f"{rate:.2f}", pct(rate, p_rate), pv(p_rate, lambda v: f"{v:.2f}"), ORANGE)
                    + kpi("Largest order", money(big["sales_amount"], 2), pct(big["sales_amount"], p_big),
                          f"{big['item_identifier']} ×{big['quantity']}", RED)
                    + kpi("Revenue per outlet", money(rpo), pct(rpo, p_rpo), f"{n_out} outlets active", GREEN)
                    + "</div>", unsafe_allow_html=True)

    # ================= trend + categories
    s = buckets(cur, start, now, freq)
    ps = buckets(prev, start - span, start, freq) if len(prev) else None
    if ps is not None:
        ps.index = ps.index + span
        ps = ps.reindex(s.index, fill_value=0)
    if len(s) > 2:                      # the newest bucket is still filling: leave it out of the chart
        s = s.iloc[:-1]
        ps = ps.iloc[:-1] if ps is not None else None

    g = (cur.groupby("item_type").agg(orders=("order_id", "count"), units=("quantity", "sum"),
                                      revenue=("sales_amount", "sum")).sort_values("revenue", ascending=False))
    g["price"] = g["revenue"] / g["units"]
    o = (cur.groupby(["outlet_identifier", "outlet_type", "outlet_location_type"])
         .agg(orders=("order_id", "count"), units=("quantity", "sum"), revenue=("sales_amount", "sum"))
         .reset_index().sort_values("revenue", ascending=False))

    # ================= graphs 1 + 2: trend and category share (donut)
    left, right = st.columns([1.6, 1])
    with left:
        with st.container(key="panel_trend"):
            panel_title("Revenue and orders over time", f"per {freq.replace('min', ' min').replace('h', ' hour')}")
            st.plotly_chart(trend_chart(s, ps), width="stretch", theme=None, config=CFG)
            st.markdown("<div class='note'>Orange: revenue · red: orders (right axis) · grey: previous period. "
                        "The newest, still-filling bucket is left out.</div>", unsafe_allow_html=True)
    with right:
        with st.container(key="panel_donut"):
            panel_title("Revenue share by category", f"top 6 of {len(g)}")
            top6, rest = g.head(6), g.iloc[6:]
            labels = top6.index.tolist() + (["Other"] if len(rest) else [])
            values = top6["revenue"].tolist() + ([rest["revenue"].sum()] if len(rest) else [])
            st.plotly_chart(donut_chart(labels, values, money(rev), "total revenue"),
                            width="stretch", theme=None, config=CFG)

    # ================= graphs 3, 4, 5: outlets, hour of day, price vs units
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(key="panel_outlet_chart"):
            panel_title("Revenue by outlet", f"{len(o)} outlets")
            st.plotly_chart(outlet_bars(o), width="stretch", theme=None, config=CFG)
    with c2:
        with st.container(key="panel_hours"):
            panel_title("Orders by hour of day", "peak hour in red")
            st.plotly_chart(hour_bars(cur), width="stretch", theme=None, config=CFG)
    with c3:
        with st.container(key="panel_bubbles"):
            panel_title("Price vs units by category", "bubble size = revenue")
            st.plotly_chart(price_bubbles(g), width="stretch", theme=None, config=CFG)

    # ================= tables: exact figures
    left, right = st.columns([1, 1])
    with left:
        with st.container(key="panel_cats"):
            panel_title("Categories", f"top 8 of {len(g)}")
            top = g.head(8)
            rows = [[name, f"{int(r.orders):,}", f"{int(r.units):,}", money(r.price, 2), money(r.revenue),
                     f"{r.revenue / rev * 100:.1f}%"] for name, r in top.iterrows()]
            st.markdown(table(["Category", "Orders", "Units", "Unit price", "Revenue", "Share"],
                              "1.5fr .8fr .8fr 1fr 1.15fr .8fr", rows, ["l", "r", "r", "r", "r", "r"],
                              bars=(top["revenue"] / top["revenue"].max() * 100).tolist()), unsafe_allow_html=True)
            rest = g.iloc[8:]
            if len(rest):
                st.markdown(f"<div class='note'>+ {len(rest)} more categories: {money(rest['revenue'].sum())} "
                            f"({rest['revenue'].sum() / rev * 100:.1f}% of revenue)</div>", unsafe_allow_html=True)
    with right:
        with st.container(key="panel_outlets"):
            panel_title("Outlets", f"{len(o)} active")
            rows = [[r.outlet_identifier, f"{r.outlet_type.replace('Supermarket ', 'SM ').replace('Grocery Store', 'Grocery')} · {r.outlet_location_type}",
                     f"{r.orders:,}", money(r.revenue / r.orders, 2), money(r.revenue), f"{r.revenue / rev * 100:.1f}%"]
                    for r in o.itertuples()]
            st.markdown(table(["Outlet", "Type · tier", "Orders", "Avg order", "Revenue", "Share"],
                              ".8fr 1.4fr .7fr .95fr 1.1fr .75fr", rows, ["l", "m", "r", "r", "r", "r"],
                              bars=(o["revenue"] / o["revenue"].max() * 100).tolist()), unsafe_allow_html=True)

    with st.container(key="panel_feed"):
        panel_title("Latest orders", "newest first")
        latest = cur.sort_values("order_time", ascending=False).head(8)
        mx = latest["sales_amount"].max() or 1
        rows = [[f"{r.order_time:%H:%M:%S}", r.item_identifier, r.item_type, r.outlet_identifier,
                 f"×{r.quantity}", money(r.unit_price, 2), money(r.sales_amount, 2)] for r in latest.itertuples()]
        st.markdown(table(["Time", "Item", "Category", "Outlet", "Qty", "Unit price", "Amount"],
                          "80px 1fr 1.6fr 1fr 50px 1fr 1fr", rows, ["m", "l", "m", "m", "m", "r", "r"],
                          bars=(latest["sales_amount"] / mx * 100).tolist()), unsafe_allow_html=True)

    with st.expander("Explore & export orders in this window"):
        show = cur.sort_values("order_time", ascending=False)
        st.dataframe(show.head(1000), hide_index=True, width="stretch")
        st.download_button(f"Export {len(show):,} orders (CSV)", show.to_csv(index=False).encode("utf-8"),
                           file_name="businessiq_orders.csv", mime="text/csv")


live_view()
