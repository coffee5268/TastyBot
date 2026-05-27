import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np


def fetch_spx_bars(days_back=25, interval='5m'):
    print(f"🔄 Fetching SPX data ({interval}, last {days_back} days)...")
    
    df = yf.download(
        tickers="^GSPC",
        period=f"{days_back}d",      # Simpler approach
        interval=interval,
        prepost=False,
        progress=False
    )
    
    print(f"✅ Raw shape: {df.shape} | Columns: {df.columns.tolist()}")
    
    # Simple and reliable cleaning for yfinance MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(0, axis=1)
    
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    
    print(f"✅ Final columns: {df.columns.tolist()}")
    print(f"✅ Loaded {len(df)} bars")
    
    return df


def create_mock_data(num_bars=1500):
    dates = pd.date_range(end=datetime.now(), periods=num_bars, freq='5min')
    np.random.seed(42)
    base = 5800 + np.cumsum(np.random.normal(1.2, 12, len(dates)))
    df = pd.DataFrame({
        'open': base,
        'high': base + np.abs(np.random.normal(8, 6, len(dates))),
        'low': base - np.abs(np.random.normal(8, 6, len(dates))),
        'close': base + np.random.normal(0.8, 7, len(dates)),
        'volume': np.random.randint(25000, 150000, len(dates))
    }, index=dates)
    df = df.between_time('09:30', '16:00')
    print(f"✅ Using {len(df)} mock SPX bars")
    return df