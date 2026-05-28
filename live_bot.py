import asyncio
from datetime import datetime
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote
>>>>>>> stream-only

async def main():
    tasty = TastySession(is_test=True)
    session = tasty.login()
    await tasty.load_accounts()
    account = tasty.accounts[0]

    strategy = OpeningRangeVWAPStrategy()
    print("🚀 SPX 0 DTE Bot - Tastytrade SANDBOX MODE (1-minute trade trigger)")

    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, ['SPX'])
        print("📡 Subscribed to live SPX quotes...")
>>>>>>> stream-only

        while True:
            try:
                quote = await streamer.get_event(Quote)
>>>>>>> stream-only
                price = getattr(quote, 'last_price', None)
                if price is None:
                    price = (getattr(quote, 'bid_price', 0) + getattr(quote, 'ask_price', 0)) / 2
                price = float(price)

                # ... existing quote handling ...
>>>>>>> stream-only

                strategy.update_with_price(price)
                strategy.get_signal(price)

                # Trade placement
                if not strategy.trade_active and (datetime.now() - strategy.start_time).seconds >= 60:
                    await strategy.place_put_credit_spread(session, account, price)

                # Check for fill + OCO
                await strategy.check_for_fill_and_place_oco(session, account)

                # Detailed status with P&L
                await strategy.print_detailed_status(session, account, price)

                strategy.print_trade_status()   # keep your old one if you want
            except Exception as e:
                print(f"Loop error: {e}")
                await asyncio.sleep(2)

            await asyncio.sleep(0.5)
>>>>>>> stream-only

if __name__ == "__main__":
    asyncio.run(main())
