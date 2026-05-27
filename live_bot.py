import asyncio
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote

async def main():
    tasty = TastySession(is_test=True)
    session = tasty.login()
    await tasty.load_accounts()

    strategy = OpeningRangeVWAPStrategy()
    print("🚀 SPX 0 DTE Bot - Tastytrade Sandbox (Live Mode)")

    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, ['SPX'])   # or '.SPX' if needed

        print("📡 Subscribed to live SPX quotes...")

        while True:
            try:
                quote = await streamer.get_event(Quote)   # or use .listen() in a loop
                price = getattr(quote, 'last_price', None)
                if price is None:
                    price = (getattr(quote, 'bid_price', 0) + getattr(quote, 'ask_price', 0)) / 2

                price = float(price)

                # Update strategy with live price
                strategy.update_with_price(price)

                # Get signal + debug prints
                signal = strategy.get_signal(price)

                if signal['action'] not in ["WAIT", "NO_BREAKOUT"]:
                    print(f"🔥 SIGNAL: {signal['action']} at {price:.2f}")

            except Exception as e:
                print(f"Quote error: {e}")
                await asyncio.sleep(2)

            await asyncio.sleep(0.5)  # adjust as needed

if __name__ == "__main__":
    asyncio.run(main())