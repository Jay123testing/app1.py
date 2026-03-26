import streamlit as st
import pandas as pd
import requests
from functools import lru_cache

st.set_page_config(page_title="Stock Portfolio Tracker", layout="wide")

st.title("📈 Stock Portfolio Tracker")
st.write("Live prices via Finnhub. Enter your Finnhub API key or set environment variable `FINNHUB_API_KEY`.")

finnhub_api_key = st.text_input("Finnhub API Key", value="", type="password")
if not finnhub_api_key:
    st.warning("Finnhub API key is required for live quotes. You can get one at https://finnhub.io.")

# User stock input area
st.header("Portfolio Positions")

default_positions = [
    {"symbol": "WTC", "name": "Wisetech Global", "exchange": "ASX", "qty": 275, "avg_cost": 30.0, "currency": "AUD", "dividend": 0.35},
    {"symbol": "WDS", "name": "Woodside Energy", "exchange": "ASX", "qty": 57, "avg_cost": 34.0, "currency": "AUD", "dividend": 0.42},
    {"symbol": "CPB", "name": "Campbell Soup Company", "exchange": "NASDAQ", "qty": 153, "avg_cost": 22.42, "currency": "USD", "dividend": 0.70},
]

if 'positions' not in st.session_state:
    st.session_state.positions = default_positions

with st.form("add_position_form"):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    symbol = col1.text_input("Symbol", value="")
    name = col2.text_input("Name", value="")
    exchange = col3.selectbox("Exchange", ["ASX", "NYSE", "NASDAQ", "Other"])
    qty = col4.number_input("Qty", min_value=0, value=1, step=1)
    avg_cost = col5.number_input("Avg Cost", min_value=0.0, value=1.0, step=0.01, format="%.4f")
    currency = col6.selectbox("Currency", ["AUD", "USD", "Other"])
    dividend = st.number_input("Expected annual dividend per share", min_value=0.0, value=0.0, step=0.01)
    submitted = st.form_submit_button("Add position")

    if submitted and symbol:
        st.session_state.positions.append({
            "symbol": symbol.strip().upper(),
            "name": name.strip() or symbol.strip().upper(),
            "exchange": exchange,
            "qty": int(qty),
            "avg_cost": float(avg_cost),
            "currency": currency,
            "dividend": float(dividend),
        })
        st.success(f"Added {symbol.upper()}")

@lru_cache(maxsize=64)
def get_quote(symbol: str, api_key: str):
    # Finnhub uses ASX ticker with .AX suffix if ASX stock
    query_symbol = symbol
    if symbol.upper().endswith(".AX"):
        query_symbol = symbol
    elif symbol.upper() in ["WTC", "WDS"]:  # ASX mapping in sample
        query_symbol = f"{symbol}.AX"

    if not api_key:
        return None

    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={query_symbol}&token={api_key}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if "c" in data and data.get("c") is not None:
            return data
        return None
    except Exception:
        return None

# AUD conversion rate
st.sidebar.header("Currency settings")
fx_usd_aud = st.sidebar.number_input("USD to AUD rate", min_value=0.0, value=1.70, step=0.001, format="%.4f")

rows = []

for p in st.session_state.positions:
    symbol = p.get("symbol")
    set_symbol = symbol
    if p.get("exchange") == "ASX" and not symbol.upper().endswith(".AX"):
        set_symbol = f"{symbol}.AX"

    quote = get_quote(set_symbol, finnhub_api_key)
    current_price = quote.get("c") if quote else None

    if current_price is None:
        # fallback to average cost if quote not available
        current_price = p.get("avg_cost")

    qty = p.get("qty", 0)
    avg_cost = p.get("avg_cost", 0.0)
    currency = p.get("currency", "AUD")

    cost_basis = avg_cost * qty
    market_value = current_price * qty
    pnl_amt = market_value - cost_basis
    pnl_pct = (pnl_amt / cost_basis * 100) if cost_basis > 0 else 0

    # Dividend after 40% tax, in local currency
    dividend_per_share = p.get("dividend", 0.0)
    total_dividend = dividend_per_share * qty
    dividend_after_tax = total_dividend * 0.60

    # USD stocks AUD equivalent
    aud_value = None
    if currency.upper() == "USD":
        aud_value = market_value * fx_usd_aud

    rows.append({
        "Symbol": symbol,
        "Name": p.get("name", ""),
        "Exchange": p.get("exchange", ""),
        "Qty": qty,
        "Avg Cost": avg_cost,
        "Current Price": current_price,
        "Currency": currency,
        "Cost Basis": cost_basis,
        "Market Value": market_value,
        "P/L Amount": pnl_amt,
        "P/L %": pnl_pct,
        "Dividend per Share": dividend_per_share,
        "Dividend Total": total_dividend,
        "Dividend After 40% Tax": dividend_after_tax,
        "AUD Value (for USD stocks)": aud_value,
    })

portfolio_df = pd.DataFrame(rows)

st.subheader("Portfolio Summary")
st.dataframe(portfolio_df.style.format({
    "Avg Cost": "{:.4f}",
    "Current Price": "{:.4f}",
    "Cost Basis": "{:.2f}",
    "Market Value": "{:.2f}",
    "P/L Amount": "{:.2f}",
    "P/L %": "{:.2f}%",
    "Dividend per Share": "{:.4f}",
    "Dividend Total": "{:.2f}",
    "Dividend After 40% Tax": "{:.2f}",
    "AUD Value (for USD stocks)": "{:.2f}",
}))

# Aggregated metrics
total_cost = portfolio_df["Cost Basis"].sum()
total_market = portfolio_df["Market Value"].sum()
total_pnl = portfolio_df["P/L Amount"].sum()
weighted_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

total_dividend_taxed = portfolio_df["Dividend After 40% Tax"].sum()

st.markdown("---")
st.subheader("Totals")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Cost Basis", f"{total_cost:.2f}")
col2.metric("Total Market Value", f"{total_market:.2f}")
col3.metric("Total P/L", f"{total_pnl:.2f}", f"{weighted_pnl_pct:.2f}%")
col4.metric("Total Dividend After Tax", f"{total_dividend_taxed:.2f}")

st.sidebar.write("## Notes")
st.sidebar.write("- ASX symbols are looked up with .AX suffix.")
st.sidebar.write("- USD stocks are converted to AUD using the provided FX rate.")
st.sidebar.write("- Dividend after tax uses 40% withholding deduction.")
