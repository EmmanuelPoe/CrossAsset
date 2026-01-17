# 💸 CrossAsset Financial Analysis Tool

CrossAsset is a lightweight, local-first Single Page Application (SPA) designed to visualize the correlation between global money supply metrics and various asset classes. 

Comparing metrics like **M2 Money Supply** or **CPI** against assets like **Gold**, **Bitcoin**, and **S&P 500** helps investors understand purchasing power, inflation trends, and macro-driven asset performance over time.

---

## 🚀 Quick Start

Launch the application with a single command:

```bash
chmod u+x run.sh
./run.sh
```

### What this script does:
1. Creates a Python virtual environment (`.venv`).
2. Installs dependencies (`streamlit`, `yfinance`, `plotly`, etc.).
3. Automatically opens your default browser to `http://localhost:8501`.
4. Starts the analysis server.

---

## 🛠 Features

### 1. Interactive Comparison
- **Reference Metrics**: Compare against M1, M2, Monetary Base, and CPI (Inflation).
- **Asset Classes**: Stocks (S&P 500, NASDAQ), Hard Assets (Gold, Silver), Commodities (Crude Oil), Forex, and Bitcoin.
- **Normalization Options**:
    - **Raw Data**: View original prices/levels.
    - **Index=100**: View performance relative to the start of the period.
    - **% Change**: Daily/Monthly percentage returns.
    - **Log Scale**: Better visualization for assets with exponential growth (like Bitcoin).

### 2. Deep Analytics
- **Time Series View**: Multi-line plotting for direct trend comparison.
- **Correlation Heatmap**: Visualizes how assets move together using Monthly Returns.
- **Scatter Analysis**: Deep-dive into the relationship between any two selected metrics with trendline analysis.
- **Rolling Correlation**: See how the relationship between money supply and an asset evolves over time.

### 3. Advanced Macro Analytics
- **🕵️ Discovery (Macro Stories)**: 1-click presets for historical regimes (e.g., "The Gold Standard", "2008 Financial Crisis", "COVID Stimulus").
- **⚖️ Real Return Mode**: Denominate any asset in terms of **Gold**, **M2 Money Supply**, or **CPI** with dense, daily-aligned math.
- **📈 Technical Overlays**: Overlay **200-day SMA** and **Bollinger Bands** to identify macro trends.
- **⏩ Lead/Lag Shift**: Find leading or lagging relationships by shifting asset prices relative to money supply data.
- **🏗 Portfolio Simulation**: Build a custom weighted basket and track its performance against the denominator of your choice.
- **🎯 Asset Sensitivity Map**: A radar chart (cluster map) visualizing how assets correlate with key macro drivers (DXY, Yield Curve, M2).
- **🤖 Macro Insights**: Contextual analysis explaining correlations, beta sensitivity, and current economic regime warnings.
- **💰 Purchasing Power Calculator**: Calculate the precise devaluation of a specific dollar amount relative to hard assets since any historical date.

### 4. Smart Timeline & Export
- **Max-First Data**: The app fetches full historical context in the background, allowing instant switching between **1Y, 5Y, 10Y, 20Y**, and **Max** without data loss.
- **Inclusive Normalization**: Every asset is indexed relative to its *own* first available price, ensuring older metrics (like M1) and newer assets (like Bitcoin) track perfectly on the same chart.
- **Custom Range**: Precise date selection for historical event analysis.
- **💾 CSV Export**: Download the fully processed and aligned dataset for offline research.

---

## 🧩 Tech Stack
- **Frontend/Backend**: Streamlit (Python)
- **Data Sourcing**: Yahoo Finance (yfinance) & FRED (CSV API)
- **Visualization**: Plotly.js
- **Data Processing**: Pandas & NumPy

---

## 🔒 Privacy & Performance
- **Ephemeral**: No long-term data storage. All data is fetched fresh on startup and stored in memory.
- **Cached**: High-performance caching ensures that UI interactions (filtering, switching views) are instantaneous once the data is initially loaded.
- **Local-First**: Runs entirely on your machine; no external accounts or API keys (FRED/Yahoo) are required.
