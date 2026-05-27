import asyncio
import pandas as pd
import matplotlib.pyplot as plt
import os
import yfinance as yf
from datetime import datetime, time
from pathlib import Path
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy

CHART_DIR = Path("charts")
CHART_DIR.mkdir(exist_ok=True)

async def update_chart(spx_price: float, or_high=None, or_low=None, vwap=None):
    fig, ax = plt.subplots(figsize=(13, 7.5))
    
    # Real data for chart
    try:
        hist = yf.download("^GSPC", period="1d", interval="5m", progress=False)
        if not hist.empty:
            # Clean columns for plotting
            if isinstance(hist.columns, pd.MultiIndex):
                hist = hist.droplevel(0, axis=1)
            ax.plot(hist.index, hist['Close'], label='SPX Price', color='blue', linewidth=2.5)
    except:
        times = pd.date_range(end=datetime.now(), periods=150, freq='1min')
        prices = [spx_price] * 150
        ax.plot(times, prices, label='SPX Price', color='blue', linewidth=2.5)

    if vwap is not None:
        ax.axhline(vwap, color='orange', linestyle='--', linewidth=2, label=f'VWAP ({vwap:.1f})')

    if or_high is not None and or_low is not None:
        ax.axhline(or_high, color='green', linestyle='--', linewidth=1.8, label=f'OR High ({or_high:.1f})')
        ax.axhline(or_low, color='red', linestyle='--', linewidth=1.8, label=f'OR Low ({or_low:.1f})')

    ax.set_title(f'SPX 0 DTE Strategy Live - {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    ax.set_ylabel('Price')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

    filename = CHART_DIR / f"spx_live_{datetime.now().strftime('%H%M')}.png"
    plt.savefig(filename, dpi=200, bbox_inches='tight')
    plt.close()

    print(f"📊 Chart updated → {filename.name}")
    try:
        os.startfile(str(filename))
    except:
        pass


async def main():
    tasty = TastySession(is_test=True)
    session = tasty.login()
    await tasty.load_accounts()
    account = tasty.get_main_account()

    strategy = OpeningRangeVWAPStrategy()
    print("🚀 SPX 0 DTE Bot - Final Clean Version")

    # Force calculation on startup
    print("📊 [STARTUP] Calculating today's OR + VWAP")
    try:
        df = yf.download("^GSPC", period="1d", interval="5m", progress=False)
        print(f"   Raw shape: {df.shape}")
        print(f"   Raw columns: {df.columns.tolist()}")

        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(0, axis=1)
            print(f"   After droplevel: {df.columns.tolist()}")

        df = df.rename(columns=str.lower)
        print(f"   After lowercase: {df.columns.tolist()}")

        strategy.calculate_or_and_vwap(df)
        print(f"   OR High: {strategy.or_high} | Low: {strategy.or_low}")
        if strategy.anchored_vwap is not None:
            print(f"   Current VWAP: {strategy.anchored_vwap.iloc[-1]:.2f}")
    except Exception as e:
        print(f"Initial calculation error: {e}")

    while True:
        now = datetime.now()

        try:
            df = yf.download("^GSPC", period="1d", interval="5m", progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.droplevel(0, axis=1)
                df = df.rename(columns=str.lower)
                price = float(df['close'].iloc[-1])
        except Exception as e:
            print(f"Data fetch error: {e}")
            price = 5820.0

        signal = strategy.get_signal(price)

        if signal['action'] in ["SELL_PUT_SPREAD", "SELL_CALL_SPREAD"]:
            print(f"🔥 SIGNAL! {signal['action']} at {price:.1f}")

        if now.minute % 15 == 0 and now.second < 15:
            await update_chart(
                spx_price=price,
                or_high=strategy.or_high,
                or_low=strategy.or_low,
                vwap=strategy.anchored_vwap.iloc[-1] if strategy.anchored_vwap is not None else None
            )

        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())