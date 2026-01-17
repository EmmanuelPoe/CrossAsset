import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from data_loader import (
    FRED_SERIES, ASSET_TICKERS, get_combined_data, normalize_data,
    calculate_technical_indicators, apply_lead_lag, calculate_portfolio,
    calculate_regression_stats
)

# Page config
st.set_page_config(page_title="Financial Asset vs Money Supply", layout="wide")

# Premium UI Constants
MACRO_STORIES = {
    "Reset": {"refs": ["M2 Money Supply"], "assets": ["Gold", "S&P 500"], "range": "10y", "denom": "USD", "mode": "Index=100"},
    "💻 Dot-Com Bubble": {"refs": ["M2 Money Supply"], "assets": ["NASDAQ 100", "S&P 500"], "range": "Custom", "start": "1995-01-01", "end": "2003-01-01", "denom": "USD", "mode": "Index=100"},
    "🏠 2008 Housing Crisis": {"refs": ["M2 Money Supply", "Median House Price"], "assets": ["S&P 500", "Gold"], "range": "Custom", "start": "2006-01-01", "end": "2013-01-01", "denom": "USD", "mode": "Index=100"},
    "🖨 Money Printer (COVID)": {"refs": ["M2 Money Supply", "Monetary Base"], "assets": ["Bitcoin", "S&P 500", "Gold"], "range": "Custom", "start": "2020-01-01", "end": "2024-01-01", "denom": "USD", "mode": "Log Scale"},
    "⚖️ The Gold Standard": {"refs": ["M2 Money Supply"], "assets": ["S&P 500", "Gold", "NASDAQ 100"], "range": "max", "denom": "Gold", "mode": "Index=100"},
}

HISTORICAL_EVENTS = [
    {"date": "2008-09-15", "label": "Lehman Brothers Bankruptcy"},
    {"date": "2020-03-15", "label": "COVID Stimulus Start"},
    {"date": "2022-03-16", "label": "Fed Begins Rate Hikes"}
]

# Theme / Custom CSS for "Ultra-Premium" Glassmorphism
st.markdown("""
<style>
    /* Premium UI cleanup */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }

    /* Glassmorphism sidebar */
    [data-testid="stSidebar"] {
        background: rgba(10, 15, 25, 0.7) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Styled metric cards */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        padding: 15px 20px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: transform 0.3s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        background: rgba(255, 255, 255, 0.05);
    }

    .main {
        background-color: #05070a;
    }
    .stApp {
        background: radial-gradient(circle at top right, #0d1117 0%, #05070a 100%);
    }
    
    h1, h2, h3, p {
        font-family: 'Outfit', 'Inter', sans-serif;
    }

    /* Neon Accent Text */
    .neon-text {
        color: #00f2ff;
        text-shadow: 0 0 10px rgba(0, 242, 255, 0.5);
    }
    
    /* Responsive adjustment for small screens */
    @media (max-width: 640px) {
        .block-container { padding: 1rem; }
    }
</style>
""", unsafe_allow_html=True)

# Session State for Story Presets
if 'current_story' not in st.session_state:
    st.session_state.current_story = "Reset"
    
def select_story(story_name):
    st.session_state.current_story = story_name
    story = MACRO_STORIES[story_name]
    # We will use these to populate the sidebar widget defaults
    st.session_state.selected_refs = story["refs"]
    st.session_state.selected_assets = story["assets"]
    st.session_state.time_range = story["range"]
    st.session_state.denominate_in = story["denom"]
    st.session_state.norm_mode = story["mode"]
    if story["range"] == "Custom":
        st.session_state.start_date = datetime.strptime(story["start"], "%Y-%m-%d")
        st.session_state.end_date = datetime.strptime(story["end"], "%Y-%m-%d")
    st.rerun()

# Header Section
st.title("💸 Cross-Asset")
st.markdown("Discover how currency debasement drives global asset prices.")

# --- Macro Stories (Collapsible) ---
with st.expander("🕵️ Discovery: Macro Stories", expanded=False):
    cols = st.columns(len(MACRO_STORIES))
    for i, story_name in enumerate(MACRO_STORIES.keys()):
        if cols[i].button(story_name, use_container_width=True):
            select_story(story_name)

# Sidebar Controls
st.sidebar.title("� Settings")
st.sidebar.caption(f"Currently viewing: {st.session_state.current_story}")

# 1. Reference Metrics
selected_refs = st.sidebar.multiselect(
    "Reference Metrics",
    options=list(FRED_SERIES.keys()),
    default=st.session_state.get('selected_refs', ["M2 Money Supply"]),
    help="Represent 'money supply' or 'inflation'. These define the value of our denominator (USD). Note: 'M1 Money Supply' had a major accounting change in May 2020, causing a vertical spike that can distort long-term charts. M2 is more consistent."
)

# 2. Asset Classes
selected_assets = st.sidebar.multiselect(
    "Assets to Track",
    options=list(ASSET_TICKERS.keys()),
    default=st.session_state.get('selected_assets', ["Gold", "S&P 500"]),
    help="Items of value people buy to preserve purchasing power."
)

# 3. Timeline
time_range = st.sidebar.selectbox(
    "Timeline",
    options=["1y", "5y", "10y", "20y", "max", "Custom"],
    index=["1y", "5y", "10y", "20y", "max", "Custom"].index(st.session_state.get('time_range', "10y")),
    help="Longer timeframes reveal deeper macro truths."
)

start_date = None
end_date = None
if time_range == "Custom":
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Start", value=st.session_state.get('start_date', datetime.now() - timedelta(days=365*10)))
    end_date = col2.date_input("End", value=st.session_state.get('end_date', datetime.now()))

# 4. Portfolio Builder
st.sidebar.divider()
st.sidebar.subheader("🏗 Portfolio Builder")
enable_portfolio = st.sidebar.checkbox("Analyze custom portfolio", help="Combine multiple assets into one 'super-asset'.")
portfolio_weights = {}
if enable_portfolio:
    for asset in selected_assets:
        portfolio_weights[asset] = st.sidebar.slider(f"Weight: {asset}", 0, 100, 50)

# 5. Technical Indicators & Visuals
st.sidebar.divider()
st.sidebar.subheader("📊 Visual Overlays")
show_sma = st.sidebar.checkbox("SMA (200-day)", help="Simple Moving Average.")
show_bb = st.sidebar.checkbox("Bollinger Bands", help="Price volatility bands.")
show_events = st.sidebar.checkbox("Show Macro Events", value=True, help="Historical markers.")
show_regimes = st.sidebar.checkbox("Show Economic Regimes", value=True, help="Highlights periods of high liquidity growth.")

# 6. Real Return (Denominator)
st.sidebar.divider()
st.sidebar.subheader("⚖️ Real Return Mode")
denominate_in = st.sidebar.selectbox(
    "Denominate Assets In:",
    options=["USD", "Gold", "M2 Money Supply", "CPI (Inflation)"],
    index=["USD", "Gold", "M2 Money Supply", "CPI (Inflation)"].index(st.session_state.get('denominate_in', "USD")),
)

# 7. Correlation Analysis
st.sidebar.divider()
st.sidebar.subheader("⏩ Lead/Lag Shift")
lead_lag_months = st.sidebar.slider("Shift Assets (Months)", -24, 24, 0)

# 8. Normalization & Scaling
st.sidebar.divider()
st.sidebar.subheader("📐 Normalization")
norm_mode = st.sidebar.radio(
    "Adjustment Mode",
    options=["Raw Data", "Index=100", "% Change", "Log Scale"],
    index=["Raw Data", "Index=100", "% Change", "Log Scale"].index(st.session_state.get('norm_mode', "Index=100")),
)

# --- Main Application Logic ---
if not selected_refs and not selected_assets:
    st.info("Please select at least one metric or asset in the sidebar.")
else:
    # Use session state to persist the view selection
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = "📈 Time Series View"

    # Fetch data (Cached)
    with st.spinner("Aligning historical data..."):
        # Always fetch maximum available history to allow flexible slicing and lead/lag
        combined_df = get_combined_data(selected_refs, selected_assets, period="max")
        
        # Slice the combined_df based on user's Timeline selection
        if not combined_df.empty:
            now = combined_df.index[-1]
            if time_range == "1y":
                combined_df = combined_df.loc[now - timedelta(days=365):]
            elif time_range == "5y":
                combined_df = combined_df.loc[now - timedelta(days=5*365):]
            elif time_range == "10y":
                combined_df = combined_df.loc[now - timedelta(days=10*365):]
            elif time_range == "20y":
                combined_df = combined_df.loc[now - timedelta(days=20*365):]
            elif time_range == "Custom":
                start_ts = pd.to_datetime(start_date)
                end_ts = pd.to_datetime(end_date)
                combined_df = combined_df.loc[start_ts:end_ts]

    if combined_df.empty:
        st.error("No data found for the selected combination and timeframe.")
    else:
        # --- APPLIED ANALYTICS ---
        
        # 1. Real Return (Denominator) Logic
        if denominate_in != "USD":
            denom_series = None
            # Case A: Denominator is already in the dataframe (it was selected by user)
            if denominate_in in combined_df.columns:
                denom_series = combined_df[denominate_in]
            
            # Case B: Denominator needs to be fetched in background
            else:
                with st.spinner(f"Fetching {denominate_in} denominator..."):
                    # Route to correct source
                    if denominate_in in FRED_SERIES:
                        denom_df = get_combined_data([denominate_in], [], period="max")
                    elif denominate_in in ASSET_TICKERS:
                        denom_df = get_combined_data([], [denominate_in], period="max")
                    else:
                        denom_df = pd.DataFrame()
                    
                    if not denom_df.empty:
                        denom_series = denom_df[denominate_in]

            if denom_series is not None:
                # CRITICAL: Densify the denominator to match daily asset data
                # Re-index to the main dataframe's daily index and forward-fill the gaps
                denom_series = denom_series.reindex(combined_df.index).ffill()
                
                # Divide and update
                combined_df = combined_df.divide(denom_series, axis=0)
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
        
        # Normalize data (using non-shifted for TS view)
        plot_df = normalize_data(shifted_df, mode=norm_mode)

        # --- Analysis Tools (Collapsible) ---
        with st.expander("🏆 Analysis: Leaderboard & Macro Insights", expanded=False):
            # --- 🏆 INFLATION DEFEATER LEADERBOARD ---
            st.subheader("🏆 The Inflation Defeater Leaderboard")
            st.caption("Which assets actually protected your purchasing power over this period?")
            
            # Calculate Returns relative to the first reference metric
            if selected_refs:
                ref_col = selected_refs[0]
                leaderboard_data = []
                
                # Start and End values for CAGR-like comparison
                start_prices = combined_df.apply(lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan)
                end_prices = combined_df.iloc[-1]
                
                ref_growth = (end_prices[ref_col] / start_prices[ref_col]) - 1
                
                for asset in selected_assets + (["🏢 Custom Portfolio"] if enable_portfolio else []):
                    if asset in combined_df.columns:
                        asset_growth = (end_prices[asset] / start_prices[asset]) - 1
                        outperformance = asset_growth - ref_growth
                        leaderboard_data.append({
                            "Asset": asset,
                            "Total Return": f"{asset_growth:.1%}",
                            "Real Return (Over {ref_col})": f"{outperformance:.1%}",
                            "Status": "✅ BEAT" if outperformance > 0 else "❌ LOST"
                        })
                
                lb_df = pd.DataFrame(leaderboard_data).sort_values("Real Return (Over {ref_col})", ascending=False)
                st.table(lb_df)

            st.divider()

            # --- 🤖 MACRO INSIGHTS ---
            st.subheader("🤖 Macro Insights")
            
            # Dynamic Insight Generation
            insights = []
            if selected_refs and selected_assets:
                # 1. Correlation Insight
                monthly_temp = shifted_df.resample('ME').last().pct_change().corr()
                top_corr_asset = selected_assets[0]
                corr_val = monthly_temp.loc[selected_refs[0], top_corr_asset]
                insights.append(f"• **Correlation**: {top_corr_asset} has a **{abs(corr_val):.0%}** {'positive' if corr_val > 0 else 'negative'} link with {selected_refs[0]}.")
                
                # 2. Beta Insight
                beta, r2 = calculate_regression_stats(shifted_df[selected_refs[0]].pct_change(), shifted_df[top_corr_asset].pct_change())
                insights.append(f"• **Sensitivity**: For every 1% move in {selected_refs[0]}, {top_corr_asset} historically moves **{beta:.2f}%**.")
                
                # 3. Regime Insight
                if "M2 Money Supply" in combined_df.columns:
                    current_m2_growth = combined_df["M2 Money Supply"].pct_change(periods=252).iloc[-1]
                    if current_m2_growth > 0.02:
                        insights.append(f"• **Regime Warning**: Current M2 growth is **{current_m2_growth:.1%}**. We are in an **'Easy Money'** environment where hard assets typically thrive.")
                    else:
                        insights.append(f"• **Regime Warning**: Current M2 growth is **{current_m2_growth:.1%}**. The macro environment is **'Tightening'**, which often pressures risk assets.")

            for insight in insights:
                st.write(insight)

        if st.session_state.view_mode == "📈 Time Series View":
            fig = go.Figure()
            
            # Base Plots (Neon Style)
            for i, col in enumerate(plot_df.columns):
                fig.add_trace(go.Scatter(
                    x=plot_df.index,
                    y=plot_df[col],
                    mode='lines',
                    name=col,
                    line=dict(width=3 if "Portfolio" in col else 2),
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
                        regime_df = get_combined_data(["M2 Money Supply"], [], period="max")
                        if not regime_df.empty:
                            # Align regime data with the active chart timeframe
                            regime_series = regime_df.loc[combined_df.index[0]:combined_df.index[-1]]["M2 Money Supply"]
                
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

            # --- 🕸️ CORRELATION SPIDER MAP ---
            st.divider()
            st.subheader("🕸️ Asset Sensitivity (Spider Map)")
            st.caption("How sensitive is each asset to the different Macro forces?")
            
            factors = ["M2 Money Supply", "CPI (Inflation)", "US Dollar Index", "Yield Curve (10Y-2Y)"]
            available_factors = [f for f in factors if f in combined_df.columns]
            
            if len(available_factors) >= 2:
                fig_spider = go.Figure()
                for asset in selected_assets:
                    values = []
                    for fact in available_factors:
                        # Use absolute correlation for spider map
                        c = combined_df[asset].pct_change().corr(combined_df[fact].pct_change())
                        values.append(abs(c))
                    
                    fig_spider.add_trace(go.Scatterpolar(
                        r=values,
                        theta=available_factors,
                        fill='toself',
                        name=asset
                    ))
                
                fig_spider.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                    template="plotly_dark",
                    showlegend=True,
                    height=500
                )
                st.plotly_chart(fig_spider, width='stretch')
            else:
                st.info("Select more Macro Reference metrics (like DXY or Yield Curve) to see the Sensitivity Spider Map.")

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
            
            # Find closest date
            start_ts = pd.to_datetime(base_date)
            idx = combined_df.index.get_indexer([start_ts], method='nearest')[0]
            
            pp_results = []
            for asset in combined_df.columns:
                start_p = combined_df[asset].iloc[idx]
                if pd.isna(start_p):
                    continue
                end_p = combined_df[asset].iloc[-1]
                change_factor = end_p / start_p
                current_value = amount / change_factor
                pp_results.append({
                    "Asset": asset,
                    "Current Value of Original $": f"${current_value:,.2f}",
                    "Purchasing Power Change": f"{(1/change_factor - 1):.2%}"
                })
            
            if pp_results:
                st.table(pd.DataFrame(pp_results))
            else:
                st.warning("No asset data available for the selected comparison date.")
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
