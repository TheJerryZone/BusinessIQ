import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="BusinessIQ | Enterprise Analytics",
    page_icon="📈",
    layout="wide"
)

# --- Custom CSS for Styling ---
st.markdown("""
    <style>
    .metric-container { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); }
    .stMetric { color: #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

# --- Database Connection ---
DB_PATH = '../database/retailiq.db'

def get_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM sales_data", conn)
        conn.close()
        # Data Cleaning
        df['item_type'] = df['item_type'].str.title()
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

# --- Load Data ---
df = get_data()

# --- Sidebar Controls ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3081/3081559.png", width=100)
st.sidebar.title("RetailIQ Control Panel")

st.sidebar.subheader(" Timeframe Filter")
year = st.sidebar.slider("Establishment Year Range", 
                         int(df["outlet_establishment_year"].min()), 
                         int(df["outlet_establishment_year"].max()), 
                         (2010, 2022))

st.sidebar.subheader(" Category Selection")
item_types = st.sidebar.multiselect("Item Category", options=df["item_type"].unique(), default=df["item_type"].unique()[:3])

st.sidebar.subheader(" Outlet Filters")
location_type = st.sidebar.radio("Location Tier", options=df["outlet_location_type"].unique())

# --- Filtering Logic ---
filtered_df = df[
    (df["item_type"].isin(item_types)) & 
    (df["outlet_location_type"] == location_type) &
    (df["outlet_establishment_year"].between(year[0], year[1]))
]

# --- UI Header ---
col_head1, col_head2 = st.columns([4, 1])
with col_head1:
    st.title(" BusinessIQ: Real - Time Business Analytics")
    st.write(f"Showing data for: {', '.join(item_types)}")
with col_head2:
    st.button("Force Refresh")
    st.write(f"Last Sync: {datetime.now().strftime('%H:%M:%S')}")

st.divider()

# --- Row 1: Advanced KPI Metrics ---
c1, c2, c3, c4 = st.columns(4)
total_sales = filtered_df["sales"].sum()
avg_sales = filtered_df["sales"].mean()
total_items = len(filtered_df)
top_cat = filtered_df.groupby("item_type")["sales"].sum().idxmax() if not filtered_df.empty else "N/A"

c1.metric("Total Revenue", f"${total_sales:,.0f}", delta="+12% vs LY")
c2.metric("Avg Transaction", f"${avg_sales:,.2f}", delta="-2% vs LW")
c3.metric("Total Volume", f"{total_items:,} units")
c4.metric("Top Category", top_cat)

st.divider()

# --- Row 2: Visual Analytics ---
row2_1, row2_2 = st.columns([2, 1])

with row2_1:
    st.subheader("Sales Trend by Outlet Type")
    fig_bar = px.bar(
        filtered_df, x="outlet_type", y="sales", 
        color="outlet_size", barmode="group",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        template="plotly_white"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with row2_2:
    st.subheader("Sales Contribution")
    fig_donut = px.pie(
        filtered_df, values="sales", names="item_fat_content", 
        hole=.6, color_discrete_sequence=['#00CC96', '#636EFA']
    )
    st.plotly_chart(fig_donut, use_container_width=True)

# --- Row 3: Deep Dive Charts ---
row3_1, row3_2 = st.columns(2)

with row3_1:
    st.subheader("Item Visibility Impact")
    fig_bubble = px.scatter(
        filtered_df, x="item_visibility", y="sales", 
        size="rating", color="item_type",
        hover_data=['item_identifier'], template="plotly_white"
    )
    st.plotly_chart(fig_bubble, use_container_width=True)

with row3_2:
    st.subheader("Top 5 Performing Products")
    top_5 = filtered_df.groupby("item_identifier")["sales"].sum().nlargest(5).reset_index()
    fig_top = px.bar(top_5, x="sales", y="item_identifier", orientation='h', color='sales')
    st.plotly_chart(fig_top, use_container_width=True)

# --- Row 4: Raw Data & Export ---
with st.expander("Explore Raw Database Records"):
    st.dataframe(filtered_df.style.highlight_max(axis=0, subset=['sales']), use_container_width=True)
    st.download_button("Export CSV", data=filtered_df.to_csv().encode('utf-8'), file_name="retail_iq_export.csv")

# --- Auto-Refresh Logic ---
time.sleep(10)
st.rerun()