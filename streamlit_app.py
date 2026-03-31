# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
from zerodha_data import load_data, get_pre_open_data_cached
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
## ⚡ Stock peer analysis
"""

# ================================
# Live Market Data Visualization
# ================================

"""
## ⚡ Live Market Data
"""

@st.cache_data(show_spinner=False, ttl=300)
def cached_get_live_nse_data(selected_index):
    from zerodha_data import get_live_nse_data
    return get_live_nse_data(selected_index)


with st.expander("", expanded=True):

    if "selected_index" not in st.session_state:
        st.session_state.selected_index = "NIFTY 50"

    index_options = ["NIFTY 500", "SECURITIES IN F&O", "NIFTY 50", "NIFTY BANK",
                    "NIFTY IT", "NIFTY AUTO", "NIFTY ENERGY", "NIFTY OIL & GAS"]

    selected_index = st.pills(
        "Select Index",
        options=sorted(set(index_options)),
        default=st.session_state.selected_index,
        key="index_pills"
    )

    if selected_index is None:
        selected_index = st.session_state.selected_index
    elif selected_index != st.session_state.selected_index:
        st.session_state.selected_index = selected_index

    try:
        result = cached_get_live_nse_data(selected_index)
        if isinstance(result, tuple) and len(result) == 5:
            df, df_advance, df_decline, percent_advance_turnover_live, percent_decline_turnover_live = result
        else:
            st.error("Unexpected data format from get_live_nse_data")
            st.stop()

        df = df.copy()
        df["%CHNG"] = pd.to_numeric(df["%CHNG"], errors="coerce")
        df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
        df = df.dropna()
        df = df[df["VALUE"] > 0]

        fno_symbols = set()
        try:
            fno_df_symbols = pd.read_csv("symbol_data/fno.csv")
            fno_symbols = set(fno_df_symbols["SYMBOL"].str.upper())
        except Exception:
            pass

        exclude_fno = False
        if st.session_state.selected_index == "NIFTY 500":
            exclude_fno = st.toggle("Exclude F&O stocks from NIFTY 500", value=True)
            if exclude_fno:
                try:
                    fno_df = pd.read_csv("symbol_data/fno.csv")
                    fno_symbols = set(fno_df["SYMBOL"].str.upper())
                    df = df[~df["SYMBOL"].str.upper().isin(fno_symbols)]
                except Exception as e:
                    st.warning(f"Could not filter F&O stocks: {e}")

        df["Color"] = df["%CHNG"].apply(lambda x: "Gain" if x > 0 else "Loss")

        max_val = max(abs(df["%CHNG"].max()), abs(df["%CHNG"].min()))
        max_val = round(max_val + 0.5)
        ticks = np.arange(-max_val, max_val + 0.5, 0.5)

        df_sorted = df.sort_values("VALUE", ascending=False).copy()
        df_sorted["SHOW_LABEL"] = False
        df_sorted["RANK"] = np.nan
        df_sorted["LABEL"] = ""

        top_n = min(20, len(df_sorted))
        df_sorted.iloc[:top_n, df_sorted.columns.get_loc("SHOW_LABEL")] = True
        df_sorted.iloc[:top_n, df_sorted.columns.get_loc("RANK")] = range(1, top_n + 1)
        df_sorted["LABEL"] = df_sorted.apply(
            lambda row: f"{int(row['RANK'])}. {row['SYMBOL']}" if row["SHOW_LABEL"] and not pd.isna(row["RANK"]) else "",
            axis=1
        )

        bubble = (
            alt.Chart(df_sorted)
            .mark_circle(opacity=0.7)
            .encode(
                x=alt.X("SYMBOL:N", axis=None),
                y=alt.Y("%CHNG:Q", title="% Change",
                        scale=alt.Scale(domain=[-max_val, max_val]),
                        axis=alt.Axis(values=ticks)),
                size=alt.Size("VALUE:Q", scale=alt.Scale(range=[200, 4000]), legend=None),
                color=alt.Color("Color:N",
                    scale=alt.Scale(domain=["Gain", "Loss"], range=["green", "red"]),
                    legend=None),
                tooltip=["SYMBOL", "%CHNG", "VALUE"]
            )
            .properties(height=600)
            .interactive()
        )

        text = (
            alt.Chart(df_sorted[df_sorted["SHOW_LABEL"]])
            .mark_text(align="center", baseline="middle", fontWeight="bold",
                       fontSize=12, dy=0, color="white")
            .encode(
                x=alt.X("SYMBOL:N", axis=None),
                y=alt.Y("%CHNG:Q"),
                text=alt.Text("LABEL:N")
            )
        )
        bubble_chart = bubble + text

        # ── Advance/Decline ─────────────────────────────────────────────
        total_count_live = df_advance + df_decline
        adv_pct_live = round(df_advance / total_count_live * 100) if total_count_live else 0
        dec_pct_live = round(df_decline / total_count_live * 100) if total_count_live else 0
        net_diff_live = adv_pct_live - dec_pct_live

        counts_df = pd.DataFrame({
            "Status": ["Advance", "Decline", "Net Diff"],
            "Count": [adv_pct_live, dec_pct_live, abs(net_diff_live)],
            "Label": [
                f"{df_advance} ({adv_pct_live}%)",
                f"{df_decline} ({dec_pct_live}%)",
                f"{'+' if net_diff_live >= 0 else '-'}{abs(net_diff_live)}%"
            ],
            "Direction": [
                "Advance", "Decline",
                "Net Positive" if net_diff_live >= 0 else "Net Negative"
            ]
        })
        bar = (
            alt.Chart(counts_df).mark_bar(cornerRadius=6)
            .encode(
                x=alt.X("Status:N", title="",
                        sort=["Advance", "Decline", "Net Diff"],
                        axis=alt.Axis(labelFontSize=13)),
                y=alt.Y("Count:Q", title="% of Total Stocks",
                        scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                color=alt.Color("Direction:N",
                    scale=alt.Scale(
                        domain=["Advance", "Decline", "Net Positive", "Net Negative"],
                        range=["#2ca02c", "#d62728", "#1f77b4", "#ff7f0e"]
                    ), legend=None),
                tooltip=["Status", "Label"],
            )
        )
        bar_text = (
            alt.Chart(counts_df).mark_text(dy=-10, color="white", size=13, fontWeight="bold")
            .encode(
                x=alt.X("Status:N", sort=["Advance", "Decline", "Net Diff"]),
                y=alt.Y("Count:Q"),
                text=alt.Text("Label:N")
            )
        )
        adv_dec_chart = (bar + bar_text).properties(height=320, title="Advance vs Decline")

        # ── Turnover Flow % ─────────────────────────────────────────────
        adv_turnover_live = df[df['%CHNG'] > 0]['VALUE'].sum()
        dec_turnover_live = df[df['%CHNG'] < 0]['VALUE'].sum()
        total_turnover_live = adv_turnover_live + dec_turnover_live
        adv_t_pct_live = round(adv_turnover_live / total_turnover_live * 100) if total_turnover_live else 0
        dec_t_pct_live = round(dec_turnover_live / total_turnover_live * 100) if total_turnover_live else 0
        net_t_diff_live = adv_t_pct_live - dec_t_pct_live

        turnover_df = pd.DataFrame({
            "Category": ["Advance", "Decline", "Net Diff"],
            "Value": [adv_t_pct_live, dec_t_pct_live, abs(net_t_diff_live)],
            "Label": [
                f"{adv_t_pct_live}%",
                f"{dec_t_pct_live}%",
                f"{'+' if net_t_diff_live >= 0 else '-'}{abs(net_t_diff_live)}%"
            ],
            "Direction": [
                "Advance", "Decline",
                "Net Positive" if net_t_diff_live >= 0 else "Net Negative"
            ]
        })
        turnover_bar = (
            alt.Chart(turnover_df).mark_bar(cornerRadius=6)
            .encode(
                x=alt.X("Category:N", title="",
                        sort=["Advance", "Decline", "Net Diff"],
                        axis=alt.Axis(labelFontSize=13)),
                y=alt.Y("Value:Q", title="% of Total Turnover",
                        scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                color=alt.Color("Direction:N",
                    scale=alt.Scale(
                        domain=["Advance", "Decline", "Net Positive", "Net Negative"],
                        range=["#2ca02c", "#d62728", "#1f77b4", "#ff7f0e"]
                    ), legend=None),
                tooltip=["Category", "Label"],
            )
            .properties(height=280, title="Turnover Flow %")
        )
        turnover_text = (
            alt.Chart(turnover_df).mark_text(dy=-10, color="white", size=13, fontWeight="bold")
            .encode(
                x=alt.X("Category:N", sort=["Advance", "Decline", "Net Diff"]),
                y=alt.Y("Value:Q"),
                text=alt.Text("Label:N")
            )
        )
        turnover_chart_live = (turnover_bar + turnover_text)

        st.markdown("### Market Bubble Chart (All Stocks)")
        with st.container(border=True):
            st.altair_chart(bubble_chart, use_container_width=True)

        col2, col3, col4 = st.columns([3, 3, 3])
        with col2:
            with st.container(border=True):
                st.altair_chart(adv_dec_chart, use_container_width=True)
        with col3:
            with st.container(border=True):
                st.altair_chart(turnover_chart_live, use_container_width=True)
        with col4:
            df_display = df.sort_values("VALUE", ascending=False).reset_index(drop=True).drop(columns=["Color"])
            st.dataframe(df_display)

        # ── Range and Turnover Bucket Charts ────────────────────────────
        bins = [-20, -10, -5, -3, -1, 0, 1, 3, 5, 10, 20]
        labels = [
            "-20% to -10%", "-10% to -5%", "-5% to -3%", "-3% to -1%", "-1% to 0%",
            "0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "10% to 20%",
        ]
        df_full_live = df.copy()
        df_full_live["range"] = pd.cut(df_full_live["%CHNG"], bins=bins, labels=labels, include_lowest=True)
        bucket_counts_live = (
            df_full_live.groupby("range", observed=False)
            .agg(count=("range", "size"), total_value=("VALUE", "sum"))
            .reset_index()
        )
        bucket_counts_live["range"] = pd.Categorical(bucket_counts_live["range"], categories=labels, ordered=True)
        bucket_counts_live = bucket_counts_live.sort_values("range")
        bucket_counts_live["total_value_label"] = bucket_counts_live["total_value"].map(lambda x: f"{x:,.0f} cr")
        bucket_counts_live["turnover_pct"] = (bucket_counts_live["total_value"] / bucket_counts_live["total_value"].sum() * 100).round(0)
        bucket_counts_live["turnover_pct_label"] = bucket_counts_live["turnover_pct"].map(lambda x: f"{int(x)}%")
        bucket_counts_live["count_pct"] = (bucket_counts_live["count"] / bucket_counts_live["count"].sum() * 100).round(0)
        bucket_counts_live["count_pct_label"] = bucket_counts_live["count_pct"].map(lambda x: f"{int(x)}%")

        range_chart_live = (
            alt.Chart(bucket_counts_live).mark_bar(cornerRadius=8)
            .encode(
                y=alt.Y("range:N", sort=labels, title="% Change Bucket",
                        axis=alt.Axis(labelFontSize=13, titleFontSize=15)),
                x=alt.X("count:Q", title="Number of Stocks",
                        axis=alt.Axis(labelFontSize=13, titleFontSize=15)),
                color=alt.condition(
                    alt.FieldOneOfPredicate(field="range", oneOf=["0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "10% to 20%"]),
                    alt.value("#2ca02c"), alt.value("#d62728"),
                ),
                tooltip=["range", "count", "count_pct_label", "total_value_label"],
            )
            .properties(title="Live Stock Count by % Change Bucket", height=360, width="container")
        )
        count_text_live = (
            alt.Chart(bucket_counts_live).mark_text(dx=5, align="left", color="white", fontWeight="bold", fontSize=13)
            .encode(
                y=alt.Y("range:N", sort=labels),
                x=alt.X("count:Q"),
                text=alt.Text("count_pct_label:N"),
            )
        )
        range_chart_live = range_chart_live + count_text_live

        turnover_range_chart_live = (
            alt.Chart(bucket_counts_live).mark_bar(cornerRadius=8)
            .encode(
                y=alt.Y("range:N", sort=labels, title="% Change Bucket",
                        axis=alt.Axis(labelFontSize=13, titleFontSize=15)),
                x=alt.X("turnover_pct:Q", title="% Share of Total Turnover",
                        axis=alt.Axis(labelFontSize=13, titleFontSize=15)),
                color=alt.condition(
                    alt.FieldOneOfPredicate(field="range", oneOf=["0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "10% to 20%"]),
                    alt.value("#1f77b4"), alt.value("#ff7f0e"),
                ),
                tooltip=["range", "total_value_label", "turnover_pct_label"],
            )
            .properties(title="Live Turnover Share by % Change Bucket", height=360, width="container")
        )
        turnover_text_live = (
            alt.Chart(bucket_counts_live).mark_text(dx=5, align="left", color="white", fontWeight="bold", fontSize=13)
            .encode(
                y=alt.Y("range:N", sort=labels),
                x=alt.X("turnover_pct:Q"),
                text=alt.Text("turnover_pct_label:N"),
            )
        )
        turnover_range_chart_live = turnover_range_chart_live + turnover_text_live

        range_col1_live, r_col2_live = st.columns([10, 10])
        with range_col1_live:
            with st.container(border=True):
                st.altair_chart(range_chart_live, use_container_width=True)
        with r_col2_live:
            with st.container(border=True):
                st.altair_chart(turnover_range_chart_live, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading live market data: {e}")


# ================================
# 🆕 Pre-open Market Movers
# ================================

"""
## ⚡ Pre-open Market Movers
"""
with st.expander("", expanded=True):
    try:
        # ── Index filter pills ──────────────────────────────────────────
        if "preopen_index" not in st.session_state:
            st.session_state.preopen_index = "ALL"

        preopen_index_options = ["ALL", "FO", "NIFTY", "BANKNIFTY", "OTHERS"]

        selected_preopen_index = st.pills(
            "Filter by Index",
            options=preopen_index_options,
            default=st.session_state.preopen_index,
            key="preopen_index_pills"
        )

        if selected_preopen_index is None:
            selected_preopen_index = st.session_state.preopen_index
        elif selected_preopen_index != st.session_state.preopen_index:
            st.session_state.preopen_index = selected_preopen_index

        # ── Price filter radio (only for ALL and OTHERS) ────────────────
        price_filter = None
        if selected_preopen_index in ("ALL", "OTHERS"):
            price_filter = st.radio(
                "Filter by Price",
                options=["No Filter", "Exclude < ₹50", "Exclude < ₹100"],
                index=0,
                horizontal=True,
                key="preopen_price_filter"
            )

        # ── Fetch data ──────────────────────────────────────────────────
        pre_open = get_pre_open_data_cached(selected_preopen_index)

        if not isinstance(pre_open, tuple) or len(pre_open) != 5 or pre_open[0].empty:
            st.warning("Pre-open data not available yet. Market may not have opened.")
        else:
            df = pre_open[0].copy()
            advance_count = pre_open[1]
            decline_count = pre_open[2]
            per_advance_turnover = pre_open[3]
            per_decline_turnover = pre_open[4]

            # ── Apply price filter ──────────────────────────────────────
            if price_filter == "Exclude < ₹50":
                df = df[df["IEP"] >= 50]
            elif price_filter == "Exclude < ₹100":
                df = df[df["IEP"] >= 100]

            if price_filter and price_filter != "No Filter":
                df_advance_rows = df[df['%CHNG'] > 0]
                df_decline_rows = df[df['%CHNG'] < 0]
                advance_count = int(len(df_advance_rows))
                decline_count = int(len(df_decline_rows))
                advance_turnover = df_advance_rows['VALUE'].sum()
                decline_turnover = df_decline_rows['VALUE'].sum()
                per_advance_turnover = int(advance_turnover / decline_turnover * 100) if decline_turnover != 0 else 0
                per_decline_turnover = int(100 - per_advance_turnover)

            if df.empty:
                st.warning("No data available for selected filter.")
            else:
                df["Color"] = df["%CHNG"].apply(lambda x: "Gain" if x > 0 else "Loss")

                # ── Pre-compute shared values ───────────────────────────
                advance_turnover_val = df[df['%CHNG'] > 0]['VALUE'].sum()
                decline_turnover_val = df[df['%CHNG'] < 0]['VALUE'].sum()
                net_flow = advance_turnover_val - decline_turnover_val

                # ══════════════════════════════════════════════════════════
                # ROW 1 — Treemap (full width)
                # ══════════════════════════════════════════════════════════
                st.markdown("### 🗺️ Market Treemap — Size = Value, Color = % Change")
                with st.container(border=True):
                    import plotly.express as px
                    fig_treemap = px.treemap(
                        df,
                        path=["SYMBOL"],
                        values="VALUE",
                        color="%CHNG",
                        color_continuous_scale="RdYlGn",
                        color_continuous_midpoint=0,
                        hover_data={"%CHNG": ":.2f", "VALUE": ":,.0f"},
                        title=f"Pre-open Treemap — {selected_preopen_index}"
                    )
                    fig_treemap.update_layout(
                        margin=dict(t=40, l=0, r=0, b=0),
                        coloraxis_colorbar=dict(title="% Chng"),
                        height=500
                    )
                    fig_treemap.update_traces(textinfo="label+value", textfont_size=13)
                    st.plotly_chart(fig_treemap, use_container_width=True)

                # ══════════════════════════════════════════════════════════
                # ROW 2 — Scatter + Advance/Decline + Turnover Flow
                # ══════════════════════════════════════════════════════════
                scatter_col, adv_col, flow_col = st.columns([5, 3, 3])

                # ── Scatter: Value vs % Change (log scale) ──────────────
                with scatter_col:
                    with st.container(border=True):
                        df_sorted = df.sort_values("VALUE", ascending=False).copy()
                        top_n = min(20, len(df_sorted))
                        df_sorted["LABEL"] = ""
                        df_sorted.iloc[:top_n, df_sorted.columns.get_loc("LABEL")] = df_sorted["SYMBOL"].iloc[:top_n]

                        scatter = (
                            alt.Chart(df_sorted)
                            .mark_circle(opacity=0.75, stroke="white", strokeWidth=0.3)
                            .encode(
                                x=alt.X("%CHNG:Q", title="% Change",
                                        axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                                y=alt.Y("VALUE:Q", title="Turnover (Cr)",
                                        scale=alt.Scale(type="log"),
                                        axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                                color=alt.Color("Color:N",
                                    scale=alt.Scale(domain=["Gain", "Loss"], range=["#2ca02c", "#d62728"]),
                                    legend=None),
                                size=alt.value(90),
                                tooltip=["SYMBOL", "%CHNG", "VALUE"]
                            )
                            .properties(height=360, title="Value vs % Change (Log Scale)")
                            .interactive()
                        )
                        scatter_labels = (
                            alt.Chart(df_sorted[df_sorted["LABEL"] != ""])
                            .mark_text(align="left", dx=6, fontSize=11, fontWeight="bold")
                            .encode(
                                x=alt.X("%CHNG:Q"),
                                y=alt.Y("VALUE:Q", scale=alt.Scale(type="log")),
                                text=alt.Text("LABEL:N"),
                                color=alt.Color("Color:N",
                                    scale=alt.Scale(domain=["Gain", "Loss"], range=["#2ca02c", "#d62728"]),
                                    legend=None)
                            )
                        )
                        st.altair_chart(scatter + scatter_labels, use_container_width=True)

                # ── Advance / Decline bar ───────────────────────────────
                with adv_col:
                    with st.container(border=True):
                        total_count = advance_count + decline_count
                        adv_count_pct = round(advance_count / total_count * 100) if total_count else 0
                        dec_count_pct = round(decline_count / total_count * 100) if total_count else 0
                        net_count_diff = adv_count_pct - dec_count_pct

                        counts_df = pd.DataFrame({
                            "Status": ["Advance", "Decline", "Net Diff"],
                            "Count": [adv_count_pct, dec_count_pct, abs(net_count_diff)],
                            "Label": [
                                f"{advance_count} ({adv_count_pct}%)",
                                f"{decline_count} ({dec_count_pct}%)",
                                f"{'+' if net_count_diff >= 0 else '-'}{abs(net_count_diff)}%"
                            ],
                            "Direction": [
                                "Advance", "Decline",
                                "Net Positive" if net_count_diff >= 0 else "Net Negative"
                            ]
                        })
                        bar = (
                            alt.Chart(counts_df).mark_bar(cornerRadius=6)
                            .encode(
                                x=alt.X("Status:N", title="",
                                        sort=["Advance", "Decline", "Net Diff"],
                                        axis=alt.Axis(labelFontSize=13)),
                                y=alt.Y("Count:Q", title="% of Total Stocks",
                                        scale=alt.Scale(domain=[0, 100]),
                                        axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                                color=alt.Color("Direction:N",
                                    scale=alt.Scale(
                                        domain=["Advance", "Decline", "Net Positive", "Net Negative"],
                                        range=["#2ca02c", "#d62728", "#1f77b4", "#ff7f0e"]
                                    ), legend=None),
                                tooltip=["Status", "Label"],
                            )
                        )
                        bar_text = (
                            alt.Chart(counts_df).mark_text(dy=-10, color="white", size=13, fontWeight="bold")
                            .encode(
                                x=alt.X("Status:N", sort=["Advance", "Decline", "Net Diff"]),
                                y=alt.Y("Count:Q"),
                                text=alt.Text("Label:N")
                            )
                        )
                        adv_dec_chart = (bar + bar_text).properties(height=320, title="Advance vs Decline")
                        st.altair_chart(adv_dec_chart, use_container_width=True)

                # ── Turnover Flow % ─────────────────────────────────────
                with flow_col:
                    with st.container(border=True):
                        total_turnover = advance_turnover_val + decline_turnover_val
                        adv_pct = round(advance_turnover_val / total_turnover * 100) if total_turnover else 0
                        dec_pct = round(decline_turnover_val / total_turnover * 100) if total_turnover else 0
                        net_diff = adv_pct - dec_pct

                        net_flow_df = pd.DataFrame({
                            "Category": ["Advance", "Decline", "Net Diff"],
                            "Value": [adv_pct, dec_pct, abs(net_diff)],
                            "Label": [
                                f"{adv_pct}%",
                                f"{dec_pct}%",
                                f"{'+' if net_diff >= 0 else '-'}{abs(net_diff)}%"
                            ],
                            "Direction": [
                                "Advance", "Decline",
                                "Net Positive" if net_diff >= 0 else "Net Negative"
                            ]
                        })
                        net_bar = (
                            alt.Chart(net_flow_df).mark_bar(cornerRadius=6)
                            .encode(
                                x=alt.X("Category:N", title="",
                                        sort=["Advance", "Decline", "Net Diff"],
                                        axis=alt.Axis(labelFontSize=12)),
                                y=alt.Y("Value:Q", title="% of Total Turnover",
                                        scale=alt.Scale(domain=[0, 100]),
                                        axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                                color=alt.Color("Direction:N",
                                    scale=alt.Scale(
                                        domain=["Advance", "Decline", "Net Positive", "Net Negative"],
                                        range=["#2ca02c", "#d62728", "#1f77b4", "#ff7f0e"]
                                    ), legend=None),
                                tooltip=["Category", "Label"]
                            )
                        )
                        net_text = (
                            alt.Chart(net_flow_df).mark_text(dy=-10, color="white", size=13, fontWeight="bold")
                            .encode(
                                x=alt.X("Category:N", sort=["Advance", "Decline", "Net Diff"]),
                                y=alt.Y("Value:Q"),
                                text=alt.Text("Label:N")
                            )
                        )
                        net_flow_chart = (net_bar + net_text).properties(height=320, title="Turnover Flow %")
                        st.altair_chart(net_flow_chart, use_container_width=True)

                # ══════════════════════════════════════════════════════════
                # ROW 3 — Bubble Chart (full width)
                # ══════════════════════════════════════════════════════════
                st.markdown("### 🫧 Bubble Chart — Size = Value, Color Intensity = % Change")
                with st.container(border=True):
                    max_val = max(abs(df["%CHNG"].max()), abs(df["%CHNG"].min()))
                    max_val = round(max_val + 0.5)
                    ticks = np.arange(-max_val, max_val + 0.5, 0.5)

                    df_sorted = df.sort_values("VALUE", ascending=False).copy()
                    df_sorted["SHOW_LABEL"] = False
                    df_sorted["RANK"] = np.nan
                    df_sorted["LABEL"] = ""

                    top_n = min(20, len(df_sorted))
                    df_sorted.iloc[:top_n, df_sorted.columns.get_loc("SHOW_LABEL")] = True
                    df_sorted.iloc[:top_n, df_sorted.columns.get_loc("RANK")] = range(1, top_n + 1)
                    df_sorted["LABEL"] = df_sorted.apply(
                        lambda row: f"{int(row['RANK'])}. {row['SYMBOL']}" if row["SHOW_LABEL"] and not pd.isna(row["RANK"]) else "",
                        axis=1
                    )

                    bubble = (
                        alt.Chart(df_sorted)
                        .mark_circle(opacity=0.8, stroke="white", strokeWidth=0.4)
                        .encode(
                            x=alt.X("SYMBOL:N", axis=None),
                            y=alt.Y("%CHNG:Q", title="% Change",
                                    scale=alt.Scale(domain=[-max_val, max_val]),
                                    axis=alt.Axis(values=ticks)),
                            size=alt.Size("VALUE:Q", scale=alt.Scale(range=[150, 4000]), legend=None),
                            color=alt.Color("%CHNG:Q",
                                scale=alt.Scale(scheme="redyellowgreen", domain=[-5, 5], clamp=True),
                                legend=alt.Legend(title="% Chng")),
                            tooltip=["SYMBOL", "%CHNG", "VALUE"]
                        )
                        .properties(height=550)
                        .interactive()
                    )
                    bubble_labels = (
                        alt.Chart(df_sorted[df_sorted["SHOW_LABEL"]])
                        .mark_text(align="center", baseline="middle", fontWeight="bold",
                                   fontSize=11, dy=0, color="white")
                        .encode(
                            x=alt.X("SYMBOL:N", axis=None),
                            y=alt.Y("%CHNG:Q"),
                            text=alt.Text("LABEL:N")
                        )
                    )
                    st.altair_chart(bubble + bubble_labels, use_container_width=True)

                # ══════════════════════════════════════════════════════════
                # ROW 4 — Range Bucket Charts + Top 15 Table
                # ══════════════════════════════════════════════════════════
                bins = [-20, -10, -5, -3, -1, 0, 1, 3, 5, 10, 20]
                labels = [
                    "-20% to -10%", "-10% to -5%", "-5% to -3%", "-3% to -1%", "-1% to 0%",
                    "0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "10% to 20%",
                ]
                df_full = df.copy()
                df_full["range"] = pd.cut(df_full["%CHNG"], bins=bins, labels=labels, include_lowest=True)
                bucket_counts = (
                    df_full.groupby("range", observed=False)
                    .agg(count=("range", "size"), total_value=("VALUE", "sum"))
                    .reset_index()
                )
                bucket_counts["range"] = pd.Categorical(bucket_counts["range"], categories=labels, ordered=True)
                bucket_counts = bucket_counts.sort_values("range")
                bucket_counts["total_value_label"] = bucket_counts["total_value"].map(lambda x: f"{x:,.0f} cr")
                bucket_counts["turnover_pct"] = (bucket_counts["total_value"] / bucket_counts["total_value"].sum() * 100).round(0)
                bucket_counts["turnover_pct_label"] = bucket_counts["turnover_pct"].map(lambda x: f"{int(x)}%")
                bucket_counts["count_pct"] = (bucket_counts["count"] / bucket_counts["count"].sum() * 100).round(0)
                bucket_counts["count_pct_label"] = bucket_counts["count_pct"].map(lambda x: f"{int(x)}%")

                range_chart = (
                    alt.Chart(bucket_counts).mark_bar(cornerRadius=8)
                    .encode(
                        y=alt.Y("range:N", sort=labels, title="% Change Bucket",
                                axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
                        x=alt.X("count:Q", title="Number of Stocks",
                                axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                        color=alt.condition(
                            alt.FieldOneOfPredicate(field="range", oneOf=["0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "10% to 20%"]),
                            alt.value("#2ca02c"), alt.value("#d62728"),
                        ),
                        tooltip=["range", "count", "count_pct_label", "total_value_label"],
                    )
                    .properties(title="Stock Count by % Change Bucket", height=360)
                )
                count_text = (
                    alt.Chart(bucket_counts).mark_text(dx=5, align="left", color="white", fontWeight="bold", fontSize=13)
                    .encode(
                        y=alt.Y("range:N", sort=labels),
                        x=alt.X("count:Q"),
                        text=alt.Text("count_pct_label:N")
                    )
                )
                range_chart = range_chart + count_text

                turnover_range_chart = (
                    alt.Chart(bucket_counts).mark_bar(cornerRadius=8)
                    .encode(
                        y=alt.Y("range:N", sort=labels, title="% Change Bucket",
                                axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
                        x=alt.X("turnover_pct:Q", title="% Share of Total Turnover",
                                axis=alt.Axis(labelFontSize=12, titleFontSize=13)),
                        color=alt.condition(
                            alt.FieldOneOfPredicate(field="range", oneOf=["0% to 1%", "1% to 3%", "3% to 5%", "5% to 10%", "10% to 20%"]),
                            alt.value("#1f77b4"), alt.value("#ff7f0e"),
                        ),
                        tooltip=["range", "total_value_label", "turnover_pct_label"],
                    )
                    .properties(title="Turnover Share by % Change Bucket", height=360)
                )
                turnover_range_text = (
                    alt.Chart(bucket_counts).mark_text(dx=5, align="left", color="white", fontWeight="bold", fontSize=13)
                    .encode(
                        y=alt.Y("range:N", sort=labels),
                        x=alt.X("turnover_pct:Q"),
                        text=alt.Text("turnover_pct_label:N")
                    )
                )
                turnover_range_chart = turnover_range_chart + turnover_range_text

                range_col1, r_col2, top10_col = st.columns([4, 4, 3])
                with range_col1:
                    with st.container(border=True):
                        st.altair_chart(range_chart, use_container_width=True)
                with r_col2:
                    with st.container(border=True):
                        st.altair_chart(turnover_range_chart, use_container_width=True)

                # ── Top 15 Value-Weighted Movers Table ──────────────────
                with top10_col:
                    with st.container(border=True):
                        st.markdown("#### 🏆 Top Movers by Value")
                        top_movers = (
                            df.sort_values("VALUE", ascending=False)
                            .head(15)[["SYMBOL", "VALUE", "%CHNG"]]
                            .reset_index(drop=True)
                        )
                        top_movers.index += 1
                        st.dataframe(
                            top_movers,
                            use_container_width=True,
                            height=360,
                            column_config={
                                "VALUE": st.column_config.ProgressColumn(
                                    "Value (Cr)",
                                    format="%.0f",
                                    min_value=0,
                                    max_value=float(top_movers["VALUE"].max())
                                ),
                                "%CHNG": st.column_config.NumberColumn(
                                    "% Change",
                                    format="%.2f%%"
                                ),
                            }
                        )

                # ══════════════════════════════════════════════════════════
                # ROW 5 — Full Data Table
                # ══════════════════════════════════════════════════════════
                with st.expander("📋 Full Data Table", expanded=False):
                    df_display = df.sort_values("VALUE", ascending=False).reset_index(drop=True).drop(columns=["Color"])
                    st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        import traceback
        st.error(f"Error loading pre-open data: {e}")
        st.code(traceback.format_exc())