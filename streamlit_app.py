# -*- coding: utf-8 -*-
# Copyright 2024-2025 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
from zerodha_data import load_data, get_pre_open_data
import requests
from io import StringIO
import numpy as np


# Calculate date ranges in yyyy-mm-dd format
today = date.today()
one_day = (today - timedelta(days=1)).strftime('%Y-%m-%d')
one_week = (today - timedelta(days=7)).strftime('%Y-%m-%d')
one_month = (today - timedelta(days=30)).strftime('%Y-%m-%d')
three_months = (today - timedelta(days=90)).strftime('%Y-%m-%d')
six_months = (today - timedelta(days=180)).strftime('%Y-%m-%d')
one_year = (today - timedelta(days=365)).strftime('%Y-%m-%d')
three_years = (today - timedelta(days=1095)).strftime('%Y-%m-%d')
five_years = (today - timedelta(days=1825)).strftime('%Y-%m-%d')
ten_years = (today - timedelta(days=3650)).strftime('%Y-%m-%d')
twenty_years = (today - timedelta(days=7300)).strftime('%Y-%m-%d')
st.set_page_config(
    page_title="Stock peer analysis dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

"""
# :material/query_stats: Stock peer analysis

Easily compare stocks against others in their peer group.
"""

""  # Add some space.

cols = st.columns([1, 3])
# Will declare right cell later to avoid showing it when no data.

STOCKS = [
    "M&M",
    "ETERNAL",
    "EICHERMOT",
    "SHRIRAMFIN",
    "INDIGO",
    "ADANIENT",
    "BAJFINANCE",
    "TMPV",
    "LT",
    "TRENT",
    "BAJAJ-AUTO",
    "HINDALCO",
    "TITAN",
    "SBIN",
    "TATASTEEL",
    "ADANIPORTS",
    "JIOFIN",
    "BAJAJFINSV",
    "SUNPHARMA",
    "DRREDDY",
    "MARUTI",
    "BHARTIARTL",
    "APOLLOHOSP",
    "ICICIBANK",
    "HINDUNILVR",
    "AXISBANK",
    "RELIANCE",
    "KOTAKBANK",
    "JSWSTEEL",
    "SBILIFE",
    "ITC",
    "GRASIM",
    "MAXHEALTH",
    "BEL",
    "HDFCBANK",
    "ASIANPAINT",
    "ULTRACEMCO",
    "COALINDIA",
    "POWERGRID",
    "CIPLA",
    "HDFCLIFE",
    "WIPRO",
    "NTPC",
    "TCS",
    "TATACONSUM",
    "NESTLEIND",
    "ONGC",
    "INFY",
    "TECHM",
    "HCLTECH"
]

DEFAULT_STOCKS = ["HDFCBANK", "TECHM", "NESTLEIND", "ULTRACEMCO", "HINDUNILVR", "RELIANCE", "ONGC"]

def stocks_to_str(stocks):
    return ",".join(stocks)

if "tickers_input" not in st.session_state:
    st.session_state.tickers_input = st.query_params.get(
        "stocks", stocks_to_str(DEFAULT_STOCKS)
    ).split(",")

# Callback to update query param when input changes
def update_query_param():
    if st.session_state.tickers_input:
        st.query_params["stocks"] = stocks_to_str(st.session_state.tickers_input)
    else:
        st.query_params.pop("stocks", None)

top_left_cell = cols[0].container(
    border=True, height="stretch"  # Removed vertical_alignment="center" as it's not valid for st.container()
)

with top_left_cell:
    # Selectbox for stock tickers
    tickers = st.multiselect(
        "Stock tickers",
        options=sorted(set(STOCKS) | set(st.session_state.tickers_input)),
        default=st.session_state.tickers_input,
        placeholder="Choose stocks to compare. Example: NVDA",
        # Removed accept_new_options=True as it's not valid for st.multiselect()
    )

# Time horizon selector
horizon_map = {
    "1 Day": one_day,
    "1 Week": one_week,
    "1 Months": one_month,
    "3 Months": three_months,
    "6 Months": six_months,
    "1 Year": one_year,
    "3 Years": three_years,
    "5 Years": five_years,
    "10 Years": ten_years,
    "20 Years": twenty_years
}

with top_left_cell:
    # Buttons for picking time horizon
    horizon = st.pills(
        "Time horizon",
        options=list(horizon_map.keys()),
        default="1 Months",
    )

# Interval selector (single select)
interval_options = ["15minute", "30minute", "60minute", "day", "week"]
with top_left_cell:
    interval = st.pills(
        "Interval",
        options=interval_options,
        default="day",
    )

tickers = [t.upper() for t in tickers]

# Update query param when text input changes
if tickers:
    st.query_params["stocks"] = stocks_to_str(tickers)
else:
    # Clear the param if input is empty
    st.query_params.pop("stocks", None)

if not tickers:
    top_left_cell.info("Pick some stocks to compare", icon=":material/info:")
    st.stop()

right_cell = cols[1].container(
    border=True, height="stretch"  # Removed vertical_alignment="center" as it's not valid
)

# load_data function is imported from zerodha_data module

# Load the data
try:
    tickers_with_nifty = tickers + ["NIFTY 50"]
    data = load_data(tickers_with_nifty, from_date=horizon_map[horizon], interval=interval)
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()

empty_columns = data.columns[data.isna().all()].tolist()

if empty_columns:
    st.error(f"Error loading data for the tickers: {', '.join(empty_columns)}.")
    st.stop()

# Normalize prices (start at 1)
normalized = data.div(data.iloc[0])

latest_norm_values = {normalized[ticker].iat[-1]: ticker for ticker in tickers}
max_norm_value = max(latest_norm_values.items())
min_norm_value = min(latest_norm_values.items())

bottom_left_cell = cols[0].container(
    border=True, height="stretch"  # Removed vertical_alignment="center"
)

with bottom_left_cell:
    cols = st.columns(2)
    cols[0].metric(
        "Best stock",
        max_norm_value[1],
        delta=f"{round(max_norm_value[0] * 100)}%",
        width="content",
    )
    cols[1].metric(
        "Worst stock",
        min_norm_value[1],
        delta=f"{round(min_norm_value[0] * 100)}%",
        width="content",
    )

# Plot normalized prices
with right_cell:
    st.altair_chart(
        alt.Chart(
            normalized.reset_index().melt(
                id_vars=["Date"], var_name="Stock", value_name="Normalized price"
            )
        )
        .mark_line()
        .encode(
            alt.X("Date:T"),
            alt.Y("Normalized price:Q").scale(zero=False),
            alt.Color("Stock:N"),
        )
        .properties(height=400)
    )

""
""

# Plot individual stock vs peer average
"""
## Individual stocks vs Nifty50

For the analysis below, each stock is compared against the Nifty50 index.
"""

if len(tickers) <= 1:
    st.warning("Pick 2 or more tickers to compare them")
    st.stop()

NUM_COLS = 4
cols = st.columns(NUM_COLS)

for i, ticker in enumerate(tickers):
    # Use Nifty50 instead of peer average
    nifty_data = normalized["NIFTY 50"]

    # Create DataFrame with Nifty50.
    plot_data = pd.DataFrame(
        {
            "Date": normalized.index,
            ticker: normalized[ticker],
            "Nifty50": nifty_data,
        }
    ).melt(id_vars=["Date"], var_name="Series", value_name="Price")

    chart = (
        alt.Chart(plot_data)
        .mark_line()
        .encode(
            alt.X("Date:T"),
            alt.Y("Price:Q").scale(zero=False),
            alt.Color(
                "Series:N",
                scale=alt.Scale(domain=[ticker, "Nifty50"], range=["red", "blue"]),
                legend=alt.Legend(orient="bottom"),
            ),
            alt.Tooltip(["Date", "Series", "Price"]),
        )
        .properties(title=f"{ticker} vs Nifty50", height=300)
    )

    cell = cols[(i * 2) % NUM_COLS].container(border=True)
    cell.write("")
    cell.altair_chart(chart, use_container_width=True)

    # Create Delta chart
    plot_data = pd.DataFrame(
        {
            "Date": normalized.index,
            "Delta": normalized[ticker] - nifty_data,
        }
    )

    chart = (
        alt.Chart(plot_data)
        .mark_area()
        .encode(
            alt.X("Date:T"),
            alt.Y("Delta:Q").scale(zero=False),
        )
        .properties(title=f"{ticker} minus Nifty50", height=300)
    )

    cell = cols[(i * 2 + 1) % NUM_COLS].container(border=True)
    cell.write("")
    cell.altair_chart(chart, use_container_width=True)

""
""

# data

# ================================
# 🆕 Pre-open Bubble Chart with Table in Columns
# ================================

"""
## ⚡ Pre-open Market Movers 


"""

try:
    pre_open = get_pre_open_data()
    df1 = pre_open[0]
    advance_count = pre_open[1]
    decline_count = pre_open[2]
    per_advance_turnover = pre_open[3]
    per_decline_turnover = pre_open[4]
    df = df1[["SYMBOL", "%CHNG", "VALUE"]].head(10).copy()

    # Build bucket ranges
    # bins = [-999, -10, -5, -3, -1, 0, 1, 3, 5, 10, 999]
    # labels = [
    #     "< -10%",
    #     "-10% to -5%",
    #     "-5% to -3%",
    #     "-3% to -1%",
    #     "-1% to 0%",
    #     "0% to 1%",
    #     "1% to 3%",
    #     "3% to 5%",
    #     "5% to 10%",
    #     "> 10%",
    # ]
    # df_full = df.copy()  # Use full df for bucketing
    # df = df.head(10)  # Keep df as head(10) for display
    # df_full["range"] = pd.cut(df_full["%CHNG"], bins=bins, labels=labels, include_lowest=True)

    # bucket_counts = df_full.groupby("range").size().reset_index(name="count")

    # # Keep sorted order
    # bucket_counts["range"] = pd.Categorical(bucket_counts["range"], categories=labels, ordered=True)
    # bucket_counts = bucket_counts.sort_values("range")

    # range_chart = (
    #     alt.Chart(bucket_counts)
    #     .mark_bar()
    #     .encode(
    #         x=alt.X("range:N", title="% Change bucket"),
    #         y=alt.Y("count:Q", title="Number of stocks"),
    #         color=alt.condition(
    #             alt.FieldOneOfPredicate(field="range", oneOf=["0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "> 10%"]),  # Fixed: use FieldOneOfPredicate for 'isin' equivalent
    #             alt.value("green"),
    #             alt.value("red"),
    #         ),
    #         tooltip=["range", "count"],
    #     )
    #     .properties(
    #         title="Pre-open Stock Count by % Change Bucket",
    #         height=320,
    #         width="container",
    #     )
    # )

    # # If you want text labels, add:
    # text = (
    #     alt.Chart(bucket_counts)
    #     .mark_text(dy=-10, color="white", fontWeight="bold")
    #     .encode(
    #         x="range:N",
    #         y="count:Q",
    #         text="count:Q",
    #     )
    # )
    # range_chart = (range_chart + text)
    # range_chart = (
    #     alt.Chart(bucket_counts)
    #     .mark_bar()
    #     .encode(
    #         x=alt.X("range:N", title="% Change bucket"),
    #         y=alt.Y("count:Q", title="Number of stocks"),
    #         color=alt.condition(
    #             alt.datum.range.isin(["0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "> 10%"]),
    #             alt.value("green"),
    #             alt.value("red"),
    #         ),
    #         tooltip=["range", "count"],
    #     )
    #     .properties(
    #         title="Pre-open Stock Count by % Change Bucket",
    #         height=320,
    #         width="container",
    #     )
    # )


    counts_df = pd.DataFrame(
        {
            "Status": ["Advance", "Decline"],
            "Count": [advance_count, decline_count],
        }
    )

    # Bar chart with bars
    bar = (
        alt.Chart(counts_df)
        .mark_bar()
        .encode(
            x=alt.X("Status:N", title="Market Direction"),
            y=alt.Y("Count:Q", title=""),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=["Advance", "Decline"], range=["green", "red"]),
                legend=None,
            ),
            tooltip=["Status", "Count"],
        )
    )

    # Text labels on bars
    text = (
        alt.Chart(counts_df)
        .mark_text(
            dy=-8,  # Position text slightly above the bar top
            color="white",
            size=14,
            fontWeight="bold",
        )
        .encode(
            x=alt.X("Status:N"),
            y=alt.Y("Count:Q"),
            text=alt.Text("Count:Q"),  # Display the count number
        )
    )

    # Combine bar and text
    adv_dec_chart = (bar + text).properties(
        height=320,
        width="container",
        title="Advance vs Decline",
    )
    # Clean data
    df = df.dropna()
    df = df[df["VALUE"] > 0]

    # Optional: Top movers only
    df = df.sort_values("%CHNG", key=abs, ascending=False).head(20)

    # Color
    df["Color"] = df["%CHNG"].apply(lambda x: "Gain" if x > 0 else "Loss")



    # Dynamic Y-axis ticks
    max_val = max(abs(df["%CHNG"].max()), abs(df["%CHNG"].min()))
    max_val = round(max_val + 0.5)
    ticks = np.arange(-max_val, max_val + 0.5, 0.5)

    # Bubble chart without legends
    bubble_chart = (
        alt.Chart(df)
        .mark_circle(opacity=0.7)
        .encode(
            x=alt.X("SYMBOL:N", title="Stock"),
            y=alt.Y(
                "%CHNG:Q",
                title="% Change",
                scale=alt.Scale(domain=[-max_val, max_val]),
                axis=alt.Axis(values=ticks)
            ),
            size=alt.Size("VALUE:Q", scale=alt.Scale(range=[100, 2000]), legend=None),
            color=alt.Color(
                "Color:N",
                scale=alt.Scale(domain=["Gain", "Loss"], range=["green", "red"]),
                legend=None
            ),
            tooltip=["SYMBOL", "%CHNG", "VALUE"]
        )
        .properties(height=400)
        .interactive()
    )

    turnover_df = pd.DataFrame({
            "Status": ["Advance", "Decline"],
            "Turnover": [per_advance_turnover, per_decline_turnover],
        })

    turnover_bar = (
        alt.Chart(turnover_df)
        .mark_bar()
        .encode(
            x=alt.X("Status:N", title="Turnover Direction"),
            y=alt.Y("Turnover:Q", title=""),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=["Advance", "Decline"], range=["green", "red"]),
                legend=None,
            ),
            tooltip=["Status", "Turnover"],
        )
        .properties(
            height=280,
            width="container",
            title="Turnover Adv Vs Dec",
        )
    )

    turnover_text = (
        alt.Chart(turnover_df)
        .mark_text(dy=-8, color="white", size=14, fontWeight="bold")
        .encode(
            x=alt.X("Status:N"),
            y=alt.Y("Turnover:Q"),
            text=alt.Text("Turnover:Q"),
        )
    )

    turnover_chart = (turnover_bar + turnover_text)

    # ------------------------------
    # Layout: 2 columns (70% chart, 30% data)
    # ------------------------------
    col1, col2, col3, col4= st.columns( [10, 3,3, 3])

    # with col1:
    #     st.altair_chart(bubble_chart, width="stretch", use_container_width=True)

    with col1:
        with st.container(border=True):
            st.altair_chart(bubble_chart, use_container_width=True)

    # with sep1:
    #     st.markdown(
    #         "<div style='width:1px; background:#CCC; height:100%; margin:0 auto;'></div>",
    #         unsafe_allow_html=True,
    #     )



    # with sep2:
    #     st.markdown(
    #         "<div style='width:1px; background:#CCC; height:100%; margin:0 auto;'></div>",
    #         unsafe_allow_html=True,
    #     )

    with col2:
        with st.container(border=True):
            st.altair_chart(adv_dec_chart, use_container_width=True)

    with col3:
        with st.container(border=True):
            st.altair_chart(turnover_chart, use_container_width=True)
    with col4:
        df.sort_values("VALUE", ascending=False, inplace=True)
        st.dataframe(df.reset_index(drop=True).drop(columns=["Color"]))
except Exception as e:
    st.error(f"Error loading pre-open data: {e}")


# ...existing code after pre-open section...

""
""

# ================================
# Live Market Data Visualization
# ================================


"""
## ⚡ Live Market Data


"""
# Index selector (single select, like stock ticker but for one index)

if "selected_index" not in st.session_state:
    st.session_state.selected_index = "NIFTY 50"  # Default

index_options = ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY AUTO"]  # Add more as needed
selected_index = st.pills(
    "Select Index",
    options=sorted(set(index_options) | {st.session_state.selected_index}),
    default=st.session_state.selected_index,
)

if selected_index:
    st.session_state.selected_index = selected_index[0] if isinstance(selected_index, list) else selected_index

try:
    from zerodha_data import get_live_nse_data
    result = get_live_nse_data(selected_index)

    if isinstance(result, tuple) and len(result) == 5:
        df, df_advance, df_decline, percent_advance_turnover_live, percent_decline_turnover_live = result
    else:
        st.error("Unexpected data format from get_live_nse_data")
        st.stop()

    # Prepare df for charts
    df = df.copy()
    df["%CHNG"] = pd.to_numeric(df["%CHNG"], errors="coerce")
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    df = df.dropna()
    df = df[df["VALUE"] > 0]
    df = df.sort_values("%CHNG", key=abs, ascending=False).head(20)
    df["Color"] = df["%CHNG"].apply(lambda x: "Gain" if x > 0 else "Loss")

    # Dynamic Y-axis ticks
    max_val = max(abs(df["%CHNG"].max()), abs(df["%CHNG"].min()))
    max_val = round(max_val + 0.5)
    ticks = np.arange(-max_val, max_val + 0.5, 0.5)

    # Bubble chart
    bubble_chart = (
        alt.Chart(df)
        .mark_circle(opacity=0.7)
        .encode(
            x=alt.X("SYMBOL:N", title="Stock"),
            y=alt.Y(
                "%CHNG:Q",
                title="% Change",
                scale=alt.Scale(domain=[-max_val, max_val]),
                axis=alt.Axis(values=ticks)
            ),
            size=alt.Size("VALUE:Q", scale=alt.Scale(range=[100, 2000]), legend=None),
            color=alt.Color(
                "Color:N",
                scale=alt.Scale(domain=["Gain", "Loss"], range=["green", "red"]),
                legend=None
            ),
            tooltip=["SYMBOL", "%CHNG", "VALUE"]
        )
        .properties(height=400)
        .interactive()
    )

    # Advance/Decline counts
    counts_df = pd.DataFrame(
        {
            "Status": ["Advance", "Decline"],
            "Count": [df_advance, df_decline],
        }
    )

    # Bar chart with bars
    bar = (
        alt.Chart(counts_df)
        .mark_bar()
        .encode(
            x=alt.X("Status:N", title="Market Direction"),
            y=alt.Y("Count:Q", title="Number of Stocks"),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=["Advance", "Decline"], range=["green", "red"]),
                legend=None,
            ),
            tooltip=["Status", "Count"],
        )
    )

    # Text labels on bars
    text = (
        alt.Chart(counts_df)
        .mark_text(
            dy=-8,
            color="white",
            size=14,
            fontWeight="bold",
        )
        .encode(
            x=alt.X("Status:N"),
            y=alt.Y("Count:Q"),
            text=alt.Text("Count:Q"),
        )
    )

    # Combine bar and text
    adv_dec_chart = (bar + text).properties(
        height=320,
        width="container",
        title="Advance vs Decline",
    )

    # # Display percent_advance_turnover as a metric
    # st.metric("Advance Turnover %", f"{percent_advance_turnover:.2f}%")

    turnover_df = pd.DataFrame({
            "Status": ["Advance", "Decline"],
            "Turnover": [percent_advance_turnover_live, percent_decline_turnover_live],
        })

    turnover_bar = (
        alt.Chart(turnover_df)
        .mark_bar()
        .encode(
            x=alt.X("Status:N", title="Turnover Direction"),
            y=alt.Y("Turnover:Q", title=""),
            color=alt.Color(
                "Status:N",
                scale=alt.Scale(domain=["Advance", "Decline"], range=["green", "red"]),
                legend=None,
            ),
            tooltip=["Status", "Turnover"],
        )
        .properties(
            height=280,
            width="container",
            title="Turnover Adv Vs Dec",
        )
    )

    turnover_text = (
        alt.Chart(turnover_df)
        .mark_text(dy=-8, color="white", size=14, fontWeight="bold")
        .encode(
            x=alt.X("Status:N"),
            y=alt.Y("Turnover:Q"),
            text=alt.Text("Turnover:Q"),
        )
    )

    turnover_chart_live = (turnover_bar + turnover_text)


    # Layout: 5 columns (chart | sep | table | sep | adv/decline)
    col1,col2, col3, col4 = st.columns( [10, 3,3, 3])

    with col1:
         with st.container(border=True):
            st.altair_chart(bubble_chart, use_container_width=True)

    # with sep1:
    #     st.markdown(
    #         "<div style='width:1px; background:#CCC; height:100%; margin:0 auto;'></div>",
    #         unsafe_allow_html=True,
    #     )


    # with sep2:
    #     st.markdown(
    #         "<div style='width:1px; background:#CCC; height:100%; margin:0 auto;'></div>",
    #         unsafe_allow_html=True,
    #     )

    with col2:
            with st.container(border=True):
                st.altair_chart(adv_dec_chart, use_container_width=True)

    with col3:
        with st.container(border=True):
            st.altair_chart(turnover_chart_live, use_container_width=True)

    with col4:
        df_display = df.sort_values("VALUE", ascending=False).reset_index(drop=True).drop(columns=["Color"])
        st.dataframe(df_display)


except Exception as e:
    st.error(f"Error loading live market data: {e}")


