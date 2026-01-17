import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from data_loader import (
    FRED_SERIES, ASSET_TICKERS, get_combined_data, normalize_data,
    calculate_technical_indicators, apply_lead_lag, calculate_portfolio,
    calculate_regression_stats
)

# Page config
st.set_page_config(page_title="Financial Asset vs Money Supply", layout="wide")

# Theme / Custom CSS for "Premium" feel & UI Cleanup
st.markdown("""
<style>
    /* Clean up Streamlit UI */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    .block-container {
        padding-top: 0rem;
        padding-bottom: 0rem;
        padding-left: 5rem;
        padding-right: 5rem;
    }

    .main {
        background-color: #0e1117;
    }
    .stApp {
        background: radial-gradient(circle at top right, #1a1c23 0%, #0e1117 100%);
    }
    h1, h2, h3 {
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    .stSidebar {
        background-color: rgba(31, 33, 40, 0.8);
        backdrop-filter: blur(10px);
    }
</style>
""", unsafe_allow_html=True)

st.title("💸 Cross-Asset Correlation Analysis")
st.markdown("Compare Money Supply metrics against real and financial assets.")

# Sidebar Controls
st.sidebar.header("Configuration")

# 1. Reference Metrics (Money Supply / CPI)
st.sidebar.subheader("Reference Metrics")
selected_refs = st.sidebar.multiselect(
    "Select Money Supply or Inflation",
    options=list(FRED_SERIES.keys()),
    default=["M2 Money Supply"],
    help="Reference metrics like M2 (Money Supply) or CPI (Inflation) represent the 'supply' side of the economy. Use these to see how asset prices react to changes in the total amount of money in circulation."
)

# 2. Asset Classes
st.sidebar.subheader("Asset Classes")
selected_assets = st.sidebar.multiselect(
    "Select Assets to Compare",
    options=list(ASSET_TICKERS.keys()),
    default=["Gold", "S&P 500"],
    help="Select one or more financial assets to track. These are the 'demand' side - items of value that you can buy with your money."
)

# 3. Time Range
st.sidebar.subheader("Timeline")
time_range = st.sidebar.selectbox(
    "Select Period",
    options=["1y", "5y", "10y", "20y", "max", "Custom"],
    index=2,
    help="Choose the historical window you want to analyze. Macro trends like money supply usually take years to play out, so longer timeframes (10Y+) are often more revealing."
)

start_date = None
end_date = None

if time_range == "Custom":
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=365*10))
    end_date = col2.date_input("End Date", datetime.now())

# 4. Portfolio Builder (New Section)
st.sidebar.divider()
st.sidebar.subheader("🏗 Portfolio Builder")
enable_portfolio = st.sidebar.checkbox("Analyze custom portfolio", help="Combine multiple assets into one 'super-asset'. For example, if you hold 50% Stocks and 50% Gold, this will show you the combined performance of that basket.")
portfolio_weights = {}

if enable_portfolio:
    for asset in selected_assets:
        weight = st.sidebar.slider(f"Weight: {asset}", 0, 100, 50)
        portfolio_weights[asset] = weight

# 5. Technical Indicators & Visuals
st.sidebar.divider()
st.sidebar.subheader("📊 Visual Overlays")
show_sma = st.sidebar.checkbox("SMA (200-day)", help="Simple Moving Average: The average price over the last 200 days. It helps smooth out daily noise to show the long-term trend. If the price is above the line, the trend is generally considered 'Up'.")
show_bb = st.sidebar.checkbox("Bollinger Bands", help="A tool that shows the 'typical' price range for an asset. If the price touches the upper or lower bands, it may be moving too fast relative to its recent history.")
show_events = st.sidebar.checkbox("Show Macro Events", value=True, help="Mark significant moments in history (like major crises or stimulus packages) to see how they impacted the data.")
show_regimes = st.sidebar.checkbox("Show Economic Regimes", help="Highlights periods of high liquidity growth (M2 > 5% annual rate). Green backgrounds indicate 'Easy Money' regimes.")

# 6. Real Return (Denominator)
st.sidebar.divider()
st.sidebar.subheader("⚖️ Real Return Mode")
denominate_in = st.sidebar.selectbox(
    "Denominate Assets In:",
    options=["USD", "Gold", "M2 Money Supply", "CPI (Inflation)"],
    index=0,
    help="By default, assets are measured in Dollars (USD). Changing this allows you to see 'Real Returns'. For example, denominating the S&P 500 in 'Gold' tells you if Stocks are actually getting more valuable, or if the Dollar is just getting weaker."
)

# 7. Correlation Analysis
st.sidebar.divider()
st.sidebar.subheader("⏩ Lead/Lag Shift")
lead_lag_months = st.sidebar.slider("Shift Assets (Months)", -24, 24, 0, help="Positive shifts OTHER assets forward (Ref leads)")

# 8. Normalization & Scaling
st.sidebar.divider()
st.sidebar.subheader("📐 Normalization & Scaling")
norm_mode = st.sidebar.radio(
    "Adjustment Mode",
    options=["Raw Data", "Index=100", "% Change", "Log Scale"],
    index=1,
    help="""
    - **Raw Data**: Actual prices/levels.
    - **Index=100**: Resets all assets to 100 at the start. Great for seeing who won the race over time!
    - **% Change**: Daily/Monthly growth rates.
    - **Log Scale**: Compresses large price jumps. Useful for comparing tiny assets with huge ones (like Bitcoin).
    """
)

# 9. Application Logic

# Main Application Constants
HISTORICAL_EVENTS = [
    {"date": "1971-08-15", "label": "Nixon shock (End of Gold Standard)"},
    {"date": "2008-09-15", "label": "Lehman Brothers Bankruptcy"},
    {"date": "2020-03-15", "label": "COVID Stimulus Start"},
    {"date": "2022-03-16", "label": "Fed Begins Rate Hikes"}
]

# Main Application Logic
if not selected_refs and not selected_assets:
    st.info("Please select at least one metric or asset in the sidebar.")
else:
    # Use session state to persist the view selection
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = "📈 Time Series View"

    # Fetch data (Cached)
    with st.spinner("Aligning historical data..."):
        fetch_period = time_range if time_range != "Custom" else "max"
        combined_df = get_combined_data(selected_refs, selected_assets, period=fetch_period)
        
        if time_range == "Custom" and not combined_df.empty:
            start_ts = pd.to_datetime(start_date)
            end_ts = pd.to_datetime(end_date)
            combined_df = combined_df.loc[start_ts:end_ts]

    if combined_df.empty:
        st.error("No data found for the selected combination and timeframe.")
    else:
        # --- APPLIED ANALYTICS ---
        
        # 1. Real Return Division
        if denominate_in != "USD":
            denom_series = None
            if denominate_in == "Gold" and "Gold" in combined_df.columns:
                denom_series = combined_df["Gold"]
            elif denominate_in in combined_df.columns:
                denom_series = combined_df[denominate_in]
            else:
                # Force fetch denominator if it wasn't selected
                with st.spinner(f"Fetching {denominate_in} for denominator..."):
                    denom_df = get_combined_data([denominate_in], [], period=fetch_period)
                    if not denom_df.empty:
                        denom_series = denom_df[denominate_in]
            
            if denom_series is not None:
                # Align and divide
                combined_df = combined_df.divide(denom_series, axis=0).dropna()
                st.info(f"Visualizing relative value in terms of **{denominate_in}**")

        # 2. Portfolio Calculation
        if enable_portfolio and portfolio_weights:
            portfolio_series = calculate_portfolio(combined_df, portfolio_weights)
            combined_df["🏢 Custom Portfolio"] = portfolio_series

        # 3. Lead/Lag Shifting
        # Positive shift means Ref LED (we pull Assets BACK in time to match Ref)
        shifted_df = apply_lead_lag(combined_df, selected_refs[0] if selected_refs else combined_df.columns[0], -lead_lag_months)

        # View Navigator (Persistent Tabs)
        st.session_state.view_mode = st.radio(
            "Select View Mode",
            options=["📈 Time Series View", "📊 Correlation Heatmap", "🎯 Scatter Analysis", "💰 Purchasing Power"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        # Normalize data based on mode (Use shifted_df so chart reflects the shift)
        plot_df = normalize_data(shifted_df, mode=norm_mode)

        if st.session_state.view_mode == "📈 Time Series View":
            st.divider()
            fig = go.Figure()
            
            # Base Plots
            for col in plot_df.columns:
                fig.add_trace(go.Scatter(
                    x=plot_df.index,
                    y=plot_df[col],
                    mode='lines',
                    name=col,
                    hovertemplate='%{y:.2f}<extra></extra>'
                ))

            # Technical Indicators
            if show_sma or show_bb:
                ti_df = calculate_technical_indicators(shifted_df)
                # Normalize TIs if needed
                if norm_mode == "Index=100":
                    ti_df = (ti_df.divide(shifted_df.iloc[0].values.repeat(3), axis=1)) * 100
                
                for asset in selected_assets:
                    if show_sma:
                        fig.add_trace(go.Scatter(
                            x=ti_df.index, y=ti_df[f"{asset}_SMA_200"],
                            name=f"{asset} 200-SMA", line=dict(dash='dot', width=1),
                            opacity=0.7
                        ))
                    if show_bb:
                        fig.add_trace(go.Scatter(
                            x=ti_df.index, y=ti_df[f"{asset}_BB_Upper"],
                            name=f"{asset} BB Upper", line=dict(width=0),
                            showlegend=False
                        ))
                        fig.add_trace(go.Scatter(
                            x=ti_df.index, y=ti_df[f"{asset}_BB_Lower"],
                            name=f"{asset} BB Lower", line=dict(width=0),
                            fill='tonexty', fillcolor='rgba(100,100,100,0.1)',
                            showlegend=False
                        ))

            # Macro Event Markers
            if show_events:
                for event in HISTORICAL_EVENTS:
                    event_date = pd.to_datetime(event['date'])
                    if event_date >= combined_df.index[0] and event_date <= combined_df.index[-1]:
                        fig.add_vline(x=event_date, line_width=1, line_dash="dash", line_color="gray")
                        fig.add_annotation(x=event_date, y=1.05, yref="paper", text=event['label'], showarrow=False, font=dict(size=10))

            # Economic Regimes Shading (Uses M2 Growth as the proxy for 'Easy Money')
            if show_regimes:
                regime_series = None
                if "M2 Money Supply" in combined_df.columns:
                    regime_series = combined_df["M2 Money Supply"]
                else:
                    # Fetch M2 specifically for shading if not selected
                    with st.spinner("Calculating regimes..."):
                        regime_df = get_combined_data(["M2 Money Supply"], [], period=fetch_period)
                        if not regime_df.empty:
                            regime_series = regime_df["M2 Money Supply"]
                
                if regime_series is not None:
                    # Calculate 1-year growth (Approx 252 trading days or 12 months)
                    # We'll use 1year lookback. 
                    m2_growth = regime_series.pct_change(periods=252) if len(regime_series) > 252 else regime_series.pct_change(periods=max(1, len(regime_series)//10))
                    easy_money = m2_growth > 0.05 # 5% growth threshold
                    
                    # Create rects for easy money periods
                    in_regime = False
                    start_date_regime = None
                    for i in range(len(easy_money)):
                        # Handle NaNs in growth
                        val = easy_money.iloc[i]
                        if pd.isna(val): continue
                        
                        if val and not in_regime:
                            in_regime = True
                            start_date_regime = easy_money.index[i]
                        elif not val and in_regime:
                            in_regime = False
                            end_date_regime = easy_money.index[i]
                            fig.add_vrect(
                                x0=start_date_regime, x1=end_date_regime,
                                fillcolor="green", opacity=0.15, line_width=0,
                                layer="below"
                            )
                    if in_regime:
                        fig.add_vrect(
                            x0=start_date_regime, x1=easy_money.index[-1],
                            fillcolor="green", opacity=0.15, line_width=0,
                            layer="below"
                        )
                    st.caption("✅ Economic Regimes: **Green zones** represent periods where M2 Money Supply grew faster than 5% per year ('Easy Money').")

            fig.update_layout(
                template="plotly_dark",
                title=f"Comparison: {', '.join(selected_refs + selected_assets)}",
                xaxis_title="Date",
                yaxis_title=norm_mode if denominate_in == "USD" else f"{norm_mode} (Real in {denominate_in})",
                height=600,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=80, b=20),
                hovermode="x unified"
            )
            st.plotly_chart(fig, width='stretch')

            # Rolling Correlation (Simple version: first ref vs first asset selected)
            if len(selected_refs) > 0 and len(selected_assets) > 0:
                st.subheader(f"Rolling Correlation: {selected_refs[0]} vs {selected_assets[0]}")
                st.info("💡 **What is Rolling Correlation?** It measures how 'synced up' two assets are over a moving window. A score of 1.0 means they move perfectly together, while -1.0 means they move in opposite directions.")
                window = st.slider("Correlation Window (Days)", 30, 365, 180, help="The number of days to look back for each correlation calculation. 180 days is a common standard for macro trends.")
                
                # Use pct change for correlation as it's better for non-stationary data
                if selected_refs[0] in combined_df.columns and selected_assets[0] in combined_df.columns:
                    corr_series = combined_df[selected_refs[0]].pct_change().rolling(window=window).corr(combined_df[selected_assets[0]].pct_change())
                    
                    fig_corr = go.Figure()
                    fig_corr.add_trace(go.Scatter(
                        x=corr_series.index,
                        y=corr_series,
                        mode='lines',
                        name=f"Rolling {window}D Corr",
                        fill='tozeroy',
                        line=dict(color='#ff7f0e')
                    ))
                    fig_corr.update_layout(
                        template="plotly_dark",
                        yaxis_title="Correlation",
                        height=300,
                        margin=dict(l=20, r=20, t=20, b=20)
                    )
                    st.plotly_chart(fig_corr, width='stretch')
                else:
                    st.warning(f"Could not calculate correlation. Missing column: {selected_refs[0] if selected_refs[0] not in combined_df.columns else selected_assets[0]}")

        elif st.session_state.view_mode == "📊 Correlation Heatmap":
            st.divider()
            st.subheader("Asset Correlation Matrix (Monthly Returns)")
            st.info("🌡️ **The Heatmap**: This grid shows how closely assets move together. **Deep Blue (+1)** means they move in lockstep. **Deep Red (-1)** means they move opposite. **White (0)** means they have no relationship. It helps you see if your portfolio is truly diversified.")
            if lead_lag_months != 0:
                st.caption(f"⚠️ Data shifted by **{lead_lag_months} months** for correlation lead/lag analysis.")
            
            # Resample to Monthly for meaningful macro correlation
            monthly_df = shifted_df.resample('ME').last()
            corr_matrix = monthly_df.pct_change().corr()
            
            fig_heatmap = go.Figure(data=go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.columns,
                colorscale='RdBu',
                zmin=-1, zmax=1,
                text=corr_matrix.round(2).values,
                texttemplate="%{text}",
                hovertemplate='X: %{x}<br>Y: %{y}<br>Corr: %{z:.2f}<extra></extra>'
            ))
            fig_heatmap.update_layout(
                template="plotly_dark",
                height=600,
                margin=dict(l=20, r=20, t=60, b=20)
            )
            st.plotly_chart(fig_heatmap, width='stretch')

        elif st.session_state.view_mode == "🎯 Scatter Analysis":
            st.divider()
            st.subheader("Scatter Relationship")
            st.info("🎯 **Scatter Analysis**: We plot the monthly changes of two items against each other. The **Trendline** shows the general relationship. If it points up, the assets tend to grow together. The tighter the dots are to the line, the stronger that relationship is.")
            if len(selected_refs + selected_assets) >= 2:
                col1, col2 = st.columns(2)
                x_axis = col1.selectbox("X-Axis Asset", options=selected_refs + selected_assets, index=0)
                y_axis = col2.selectbox("Y-Axis Asset", options=selected_refs + selected_assets, index=min(1, len(selected_refs + selected_assets) - 1))
                
                if x_axis == y_axis:
                    st.warning("Please select two different assets for comparison.")
                else:
                    # Resample for cleaner scatter plots
                    scatter_df = shifted_df[[x_axis, y_axis]].resample('ME').last().pct_change().dropna()
                    
                    fig_scatter = go.Figure()
                    fig_scatter.add_trace(go.Scatter(
                        x=scatter_df[x_axis],
                        y=scatter_df[y_axis],
                        mode='markers+text',
                        marker=dict(size=10, color='#636EFA', opacity=0.6, line=dict(width=1, color='White')),
                        hovertemplate=f'{x_axis}: %{{x:.2%}}<br>{y_axis}: %{{y:.2%}}<extra></extra>'
                    ))
                    
                    # Add trendline (manually using numpy)
                    import numpy as np
                    if not scatter_df.empty:
                        m, b = np.polyfit(scatter_df[x_axis], scatter_df[y_axis], 1)
                        fig_scatter.add_trace(go.Scatter(
                            x=scatter_df[x_axis],
                            y=m*scatter_df[x_axis] + b,
                            mode='lines',
                            name='Trendline',
                            line=dict(color='red', dash='dash')
                        ))

                    fig_scatter.update_layout(
                        template="plotly_dark",
                        xaxis_title=f"{x_axis} % Change (Monthly)",
                        yaxis_title=f"{y_axis} % Change (Monthly)",
                        height=600
                    )
                    
                    # Display Stats
                    beta, r_squared = calculate_regression_stats(scatter_df[x_axis], scatter_df[y_axis])
                    c1, c2 = st.columns(2)
                    c1.metric("Beta (Sensitivity)", f"{beta:.2f}", help="How much the Y-axis asset moves for every 1% move in the X-axis asset.")
                    c2.metric("R-Squared (Explanatory Power)", f"{r_squared:.2%}", help="How much of the movement in the Y-axis asset is explained by the X-axis asset. 100% means a perfect mathematical link.")
                    
                    st.plotly_chart(fig_scatter, width='stretch')
            else:
                st.info("Select at least two assets to view scatter analysis.")

        elif st.session_state.view_mode == "💰 Purchasing Power":
            st.divider()
            st.subheader("💸 Purchasing Power Calculator")
            st.write("How has the value of your cash changed relative to these assets?")
            st.info("🧪 **Calculation**: We take your cash amount and divide it by the price growth of each asset. It answers the question: *'If I saved $1000 in a shoebox, how much [Gold/Stock/Bitcoin] would that $1000 buy today compared to back then?'*")
            
            col1, col2 = st.columns(2)
            amount = col1.number_input("Original Amount ($)", value=1000.0)
            base_date = col2.date_input("Comparison Start Date", value=combined_df.index[0])
            
            # Find closest date in index
            start_ts = pd.to_datetime(base_date)
            if start_ts < combined_df.index[0]:
                st.warning("Start date is before available data. Using earliest possible date.")
                start_ts = combined_df.index[0]
            
            idx = combined_df.index.get_indexer([start_ts], method='nearest')[0]
            start_prices = combined_df.iloc[idx]
            current_prices = combined_df.iloc[-1]
            
            # Change in purchasing power
            pp_results = []
            for asset in combined_df.columns:
                change_factor = current_prices[asset] / start_prices[asset]
                current_value = amount / change_factor
                pp_results.append({
                    "Asset": asset,
                    "Current Value of Original $": f"${current_value:,.2f}",
                    "Purchasing Power Change": f"{(1/change_factor - 1):.2%}"
                })
            
            st.table(pd.DataFrame(pp_results))
            st.info(f"Summary: A ${amount:,.0f} sum from {combined_df.index[idx].strftime('%Y-%m-%d')} is now worth the amounts above in terms of the assets' current prices.")

        # 9. Export Data (Sidebar)
        st.sidebar.divider()
        st.sidebar.subheader("💾 Export Data")
        csv = combined_df.to_csv().encode('utf-8')
        st.sidebar.download_button(
            label="Download Aligned CSV",
            data=csv,
            file_name="cross_asset_data.csv",
            mime="text/csv",
            key="export_csv"
        )

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Data sourced from FRED and Yahoo Finance. All data is fetched on startup and not stored permanently.")
