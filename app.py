import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from data_loader import FRED_SERIES, ASSET_TICKERS, get_combined_data, normalize_data

# Page config
st.set_page_config(page_title="Financial Asset vs Money Supply", layout="wide")

# Theme / Custom CSS for "Premium" feel
st.markdown("""
<style>
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
    default=["M2 Money Supply"]
)

# 2. Asset Classes
st.sidebar.subheader("Asset Classes")
selected_assets = st.sidebar.multiselect(
    "Select Assets to Compare",
    options=list(ASSET_TICKERS.keys()),
    default=["Gold", "S&P 500"]
)

# 3. Time Range
st.sidebar.subheader("Timeline")
time_range = st.sidebar.selectbox(
    "Select Period",
    options=["1y", "5y", "10y", "20y", "max", "Custom"],
    index=2
)

start_date = None
end_date = None

if time_range == "Custom":
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=365*10))
    end_date = col2.date_input("End Date", datetime.now())

# 4. Normalization
st.sidebar.subheader("Normalization & Scaling")
norm_mode = st.sidebar.radio(
    "Adjustment Mode",
    options=["Raw Data", "Index=100", "% Change", "Log Scale"],
    index=1
)

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
        # View Navigator (Persistent Tabs)
        st.session_state.view_mode = st.radio(
            "Select View Mode",
            options=["📈 Time Series View", "📊 Correlation Heatmap", "🎯 Scatter Analysis"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        # Normalize data based on mode
        plot_df = normalize_data(combined_df, mode=norm_mode)

        if st.session_state.view_mode == "📈 Time Series View":
            st.divider()
            fig = go.Figure()
            
            for col in plot_df.columns:
                fig.add_trace(go.Scatter(
                    x=plot_df.index,
                    y=plot_df[col],
                    mode='lines',
                    name=col,
                    hovertemplate='%{y:.2f}<extra></extra>'
                ))

            fig.update_layout(
                template="plotly_dark",
                title=f"Comparison: {', '.join(selected_refs + selected_assets)}",
                xaxis_title="Date",
                yaxis_title=norm_mode,
                height=600,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=60, b=20),
                hovermode="x unified"
            )
            st.plotly_chart(fig, width='stretch')

            # Rolling Correlation (Simple version: first ref vs first asset selected)
            if len(selected_refs) > 0 and len(selected_assets) > 0:
                st.subheader(f"Rolling Correlation: {selected_refs[0]} vs {selected_assets[0]}")
                window = st.slider("Correlation Window (Days)", 30, 365, 180)
                
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
            st.markdown("""
            *Note: Correlations are calculated on **monthly percentage changes** to align smoothed macro data (M2/CPI) with daily financial assets.*
            """)
            
            # Resample to Monthly for meaningful macro correlation
            monthly_df = combined_df.resample('ME').last()
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
            if len(selected_refs + selected_assets) >= 2:
                col1, col2 = st.columns(2)
                x_axis = col1.selectbox("X-Axis Asset", options=selected_refs + selected_assets, index=0)
                y_axis = col2.selectbox("Y-Axis Asset", options=selected_refs + selected_assets, index=min(1, len(selected_refs + selected_assets) - 1))
                
                if x_axis == y_axis:
                    st.warning("Please select two different assets for comparison.")
                else:
                    # Resample for cleaner scatter plots
                    scatter_df = combined_df[[x_axis, y_axis]].resample('ME').last().pct_change().dropna()
                    
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
                    st.plotly_chart(fig_scatter, width='stretch')
            else:
                st.info("Select at least two assets to view scatter analysis.")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Data sourced from FRED and Yahoo Finance. All data is fetched on startup and not stored permanently.")
