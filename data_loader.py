import pandas as pd
import yfinance as yf
import requests
import io
import streamlit as st
from datetime import datetime, timedelta

# FRED Series IDs
FRED_SERIES = {
    "M1 Money Supply": "M1SL",
    "M2 Money Supply": "M2SL",
    "Monetary Base": "BOGMBASE",
    "CPI (Inflation)": "CPIAUCSL",
    "Median House Price": "MSPUS",
    "US Dollar Index": "DTWEXBGS",
    "Yield Curve (10Y-2Y)": "T10Y2Y",
    "Fed Funds Rate": "FEDFUNDS",
    "M2 Money Velocity": "M2V",
}

# Yahoo Finance Tickers
ASSET_TICKERS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "S&P 500": "^GSPC",
    "NASDAQ 100": "^IXIC",
    "Dow Jones": "^DJI",
    "10Y Treasury Yield": "^TNX",
    "Bitcoin": "BTC-USD",
    "Crude Oil": "CL=F",
    "EUR/USD": "EURUSD=X",
}

def fetch_fred_data(series_id):
    """Fetch data from FRED using the CSV download link."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        # FRED CSVs use 'observation_date' as the header
        date_col = 'observation_date' if 'observation_date' in df.columns else 'DATE'
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col)
        # Handle cases where value might be '.'
        df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
        return df.dropna()
    except Exception as e:
        st.error(f"Error fetching FRED data for {series_id}: {e}")
        return pd.DataFrame()

def fetch_yfinance_data(ticker, period="max"):
    """Fetch data from Yahoo Finance."""
    try:
        data = yf.download(ticker, period=period)
        if data.empty:
            return pd.DataFrame()
        
        # Handle potential MultiIndex columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        if 'Close' in data.columns:
            df = data[['Close']].copy()
        elif 'Adj Close' in data.columns:
            df = data[['Adj Close']].copy()
        else:
            return pd.DataFrame()

        df.index = pd.to_datetime(df.index)
        # Ensure the index is timezone naive for consistency
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.columns = [ticker]
        return df
    except Exception as e:
        st.error(f"Error fetching YFinance data for {ticker}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_combined_data(fred_series_list, asset_ticker_list, period="10y"):
    """
    Fetch all requested data and align dates.
    Returns a multi-column DataFrame.
    """
    # Convert list to tuple for caching (lists are not hashable)
    fred_series_list = tuple(fred_series_list)
    asset_ticker_list = tuple(asset_ticker_list)
    
    all_dfs = []
    
    # Fetch FRED data
    for name in fred_series_list:
        series_id = FRED_SERIES.get(name)
        if series_id:
            df = fetch_fred_data(series_id)
            if not df.empty:
                df.columns = [name]
                all_dfs.append(df)
    
    # Fetch Asset data
    for name in asset_ticker_list:
        ticker = ASSET_TICKERS.get(name)
        if ticker:
            df = fetch_yfinance_data(ticker, period=period)
            if not df.empty:
                df.columns = [name]
                all_dfs.append(df)
    
    if not all_dfs:
        return pd.DataFrame()
    
    # Merge all dataframes on index
    combined_df = pd.concat(all_dfs, axis=1)
    
    # Forward fill missing values (common in macro data vs daily assets)
    combined_df = combined_df.ffill()
    
    # Drop rows where EVERYTHING is NaN (no data for any selected metric)
    # This prevents the chart from being clipped to the youngest asset's start date.
    # Older assets (like Gold/S&P) will now show their full history since 1970s.
    combined_df = combined_df.dropna(how='all')
    
    return combined_df

def normalize_data(df, mode="Index=100"):
    """
    Normalize the dataframe based on the selected mode.
    """
    if df.empty:
        return df
        
    if mode == "Index=100":
        # Normalize each column relative to its first available value
        return (df / df.apply(lambda x: x.dropna().iloc[0] if not x.dropna().empty else 1)) * 100
    elif mode == "% Change":
        return df.pct_change() * 100
    elif mode == "Log Scale":
        import numpy as np
        return np.log(df)
    
    return df

def calculate_technical_indicators(df, window=200):
    """Calculate SMA and Bollinger Bands for each column."""
    results = {}
    for col in df.columns:
        # Standardize data to numeric to avoid rolling mean errors on mixed types
        series = pd.to_numeric(df[col], errors='coerce')
        sma = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        results[f"{col}_SMA_{window}"] = sma
        results[f"{col}_BB_Upper"] = sma + (std * 2)
        results[f"{col}_BB_Lower"] = sma - (std * 2)
    return pd.DataFrame(results, index=df.index)

def apply_lead_lag(df, focus_col, shift_months=0):
    """
    Shifts the entire dataframe EXCEPT the focus_col by shift_months.
    Focus_col is typically the Money Supply metric.
    """
    if shift_months == 0:
        return df
    
    shifted_df = df.copy()
    other_cols = [c for c in df.columns if c != focus_col]
    
    shifted_df[other_cols] = shifted_df[other_cols].shift(shift_months * 30)
    return shifted_df.dropna(how='all')

def calculate_portfolio(df, weights_dict):
    """Calculate a weighted portfolio index from columns."""
    if not weights_dict:
        return pd.Series(0.0, index=df.index)
        
    result = pd.Series(0.0, index=df.index)
    total_weight = sum(weights_dict.values())
    if total_weight == 0:
        return result
        
    for asset, weight in weights_dict.items():
        if asset in df.columns:
            # Normalize each asset to 100 at start of the visible slice for weighted sum
            first_val = df[asset].iloc[0]
            if first_val != 0:
                normalized = (df[asset] / first_val) * 100
                result += normalized * (weight / total_weight)
    return result

def calculate_regression_stats(x_series, y_series):
    """
    Calculate Beta and R-Squared for two series.
    Assumes series are already aligned and percentage changes.
    """
    import numpy as np
    from sklearn.linear_model import LinearRegression
    
    # Drop NAs
    df = pd.DataFrame({'x': x_series, 'y': y_series}).dropna()
    if df.empty or len(df) < 2:
        return 0, 0
    
    X = df[['x']].values
    y = df['y'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    beta = model.coef_[0]
    r_squared = model.score(X, y)
    
    return beta, r_squared
