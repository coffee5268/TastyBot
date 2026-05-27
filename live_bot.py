import asyncio
import pandas as pd
from datetime import datetime
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote   # For live quotes

async def main():
    tasty = TastySession(is_test=True)   # Sandbox
    session = tasty.login()
    await tasty.load_accounts()

    strategy = OpeningRangeVWAPStrategy()
    print("🚀 SPX 0 DTE Bot - Tastytrade Sandbox Version")

    # Initial OR + VWAP calculation
    print("📊 [STARTUP] Calculating today's OR + VWAP...")
    try:
        df = yf.download("^GSPC", period="5d", interval="5m", progress=False)
        
        print(f"   Raw shape: {df.shape}")
        print(f"   Raw columns: {df.columns.tolist()}")
        
        # === ROBUST COLUMN CLEANING ===
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(0, axis=1)          # Remove ticker level
        
        # Force standard column names (this fixes your current issue)
        df.columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        df = df.rename(columns=str.lower)
        
        print(f"   After cleaning → Columns: {df.columns.tolist()}")
        print(f"   Downloaded {len(df)} bars")
        
        strategy.calculate_or_and_vwap(df)
        
    except Exception as e:
        print(f"Initial calculation error: {e}")
        import traceback
        traceback.print_exc()

    # Live streaming with tastytrade
    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, ['SPX'])   # or '^GSPC' / 'SPX' — test symbol

        while True:
            try:
                quote = await streamer.get_event(Quote)
                price = float(quote.last_price) if hasattr(quote, 'last_price') else float(quote.bid_price + quote.ask_price)/2
                
                signal = strategy.get_signal(price)

                if signal['action'] in ["SELL_PUT_SPREAD", "SELL_CALL_SPREAD"]:
                    print(f"🔥 SIGNAL! {signal['action']} at {price:.1f}")

            except Exception as e:
                print(f"Quote error: {e}")
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(5)  # Adjust as needed

if __name__ == "__main__":
    asyncio.run(main())