"""Streamlit dashboard for the FX Treasury Engine."""

import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import Any

from src.models.types import Currency, DataSource, RateType
from src.core.config import get_config
from src.core.engine import FXTreasuryEngine


st.set_page_config(
    page_title="FX Treasury Engine",
    page_icon="💱",
    layout="wide",
)


@st.cache_data(ttl=60)
def get_analysis() -> dict[str, Any]:
    """Run analysis and cache results."""
    engine = FXTreasuryEngine()
    return asyncio.run(engine.run_analysis())


def render_rate_table(rates: list[dict]) -> pd.DataFrame:
    """Convert rates to DataFrame for display."""
    if not rates:
        return pd.DataFrame()

    rows = []
    for r in rates:
        rows.append({
            "Source": r.get("source"),
            "Base": r.get("base_currency"),
            "Target": r.get("target_currency"),
            "Rate": float(r.get("rate", 0)),
            "Type": r.get("rate_type"),
            "Timestamp": r.get("timestamp"),
        })
    return pd.DataFrame(rows)


def render_signals_table(signals: list[dict]) -> pd.DataFrame:
    """Convert signals to DataFrame for display."""
    if not signals:
        return pd.DataFrame()

    rows = []
    for s in signals:
        rows.append({
            "Base": s.get("base_currency"),
            "Target": s.get("target_currency"),
            "Action": s.get("recommended_action"),
            "Spread (bps)": float(s.get("spread_bps", 0)),
            "Confidence": float(s.get("confidence", 0)),
            "Expected Savings (USD)": float(s.get("expected_savings_usd", 0)),
            "Sources": ", ".join(s.get("sources", [])),
        })
    return pd.DataFrame(rows)


def render_exposure_table(exposure: dict[str, Decimal]) -> pd.DataFrame:
    """Convert exposure to DataFrame."""
    rows = []
    for currency, amount in exposure.items():
        rows.append({
            "Currency": currency,
            "Exposure (USD)": float(amount),
        })
    return pd.DataFrame(rows)


def main():
    """Main dashboard entry point."""
    st.title("💱 Cross-Border FX & Treasury Risk Engine")
    st.markdown(
        "*Real-time FX arbitrage detection, exposure tracking, and margin protection*"
    )

    # Sidebar
    st.sidebar.header("Configuration")
    auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", value=True)
    if st.sidebar.button("Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    # Show last updated
    st.sidebar.caption(f"Last updated: {datetime.utcnow().strftime('%H:%M:%S UTC')}")

    # Run analysis
    with st.spinner("Fetching rates and analyzing..."):
        results = get_analysis()

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Sources Fetched", results["source_count"])
    with col2:
        st.metric("Arbitrage Signals", results["signal_count"])
    with col3:
        total_exp = results["exposure"].get("total_usd", 0)
        st.metric("Total Exposure (USD)", f"${float(total_exp):,.2f}")
    with col4:
        adj_exp = results["inflation_adjusted_exposure"].get("total_usd", 0)
        st.metric("Inflation-Adjusted (USD)", f"${float(adj_exp):,.2f}")

    # Rates section
    st.header("📊 Exchange Rates")
    all_rates = []
    for collection in results["collections"]:
        for rate in collection["rates"]:
            rate["source"] = collection["source"]
            all_rates.append(rate)

    rates_df = render_rate_table(all_rates)
    if not rates_df.empty:
        st.dataframe(rates_df, use_container_width=True, hide_index=True)
    else:
        st.info("No rates available")

    # Arbitrage signals
    st.header("⚡ Arbitrage Signals")
    signals = results["arbitrage_signals"]
    signals_df = render_signals_table(signals)
    if not signals_df.empty:
        # Highlight by confidence
        def highlight_confidence(val):
            if val >= 0.8:
                return "background-color: #d4edda"
            elif val >= 0.5:
                return "background-color: #fff3cd"
            return "background-color: #f8d7da"

        st.dataframe(
            signals_df.style.applymap(highlight_confidence, subset=["Confidence"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No arbitrage signals detected")

    # Exposure tracking
    st.header("💼 Treasury Exposure")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Nominal Exposure (USD)")
        exp_df = render_exposure_table(results["exposure"])
        if not exp_df.empty:
            st.dataframe(exp_df, use_container_width=True, hide_index=True)
        else:
            st.info("No positions tracked")

    with col2:
        st.subheader("Inflation-Adjusted Exposure (USD)")
        adj_df = render_exposure_table(results["inflation_adjusted_exposure"])
        if not adj_df.empty:
            st.dataframe(adj_df, use_container_width=True, hide_index=True)
        else:
            st.info("No positions tracked")

    # Source status
    st.header("🔗 Data Source Status")
    config = get_config()
    for name, source in config.sources.items():
        status = "🟢 Active" if source.enabled else "🔴 Disabled"
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{name}**")
        with col2:
            st.write(status)

    # ROI Pitch
    st.header("💰 ROI Pitch")
    st.markdown(
        """
        > *"I built a multi-currency treasury pipeline integrating Fed rates, ECB FX data, 
        and emerging-market central bank APIs to track real-time FX exposure and inflation 
        erosion—helping global finance teams protect margins and optimize cross-border liquidity."*
        """
    )

    if auto_refresh:
        st.rerun()


if __name__ == "__main__":
    main()