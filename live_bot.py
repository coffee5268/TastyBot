import asyncio
import pandas as pd
from datetime import datetime
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote
from data_fetch import fetch_spx_bars_tasty  # new tasty fetch

async def main():
    tasty = TastySession(is_test=True)
    session = tasty.login()
    await tasty.load_accounts()

    strategy = OpeningRangeVWAPStrategy()
    print("🚀 SPX 0 DTE Bot - Tastytrade Sandbox")

    # Initial OR + VWAP using tastytrade data
    print("📊 [STARTUP] Calculating today's OR + VWAP...")
    try:
        df = await fetch_spx_bars_tasty(session, days_back=2, interval='5m')
        if not df.empty:
            strategy.calculate_or_and_vwap(df)
        else:
            print("⚠️ Using placeholder OR/VWAP for testing live quotes...")
            # Temporary placeholders so live loop runs
            strategy.or_high = 5350.0
            strategy.or_low = 5300.0
            strategy.anchored_vwap = pd.Series([5325.0])
    except Exception as e:
        print(f"Initial data error: {e}")
        # ... placeholders ...

    # Live quotes
    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, ['SPX'])  # confirm symbol works in sandbox

        while True:
            try:
                quote = await streamer.get_event(Quote)
                # Mid or last price
                price = getattr(quote, 'last_price', None)
                if price is None:
                    price = (getattr(quote, 'bid_price', 0) + getattr(quote, 'ask_price', 0)) / 2
                price = float(price)

                signal = strategy.get_signal(price)

                if signal['action'] in ["SELL_PUT_SPREAD", "SELL_CALL_SPREAD"]:
                    print(f"🔥 SIGNAL! {signal['action']} at {price:.1f}")
                    # TODO: place order via tasty API

            except Exception as e:
                print(f"Quote error: {e}")
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(1)  # faster polling if needed

if __name__ == "__main__":
    asyncio.run(main())