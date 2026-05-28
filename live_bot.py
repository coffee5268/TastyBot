import asyncio
from datetime import datetime
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote

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

        while True:
            try:
                quote = await streamer.get_event(Quote)
                price = getattr(quote, 'last_price', None)
                if price is None:
                    price = (getattr(quote, 'bid_price', 0) + getattr(quote, 'ask_price', 0)) / 2
                price = float(price)

                strategy.update_with_price(price)
                strategy.get_signal(price)

                # === TRADE TRIGGER DEBUG ===
                elapsed = (datetime.now() - strategy.start_time).seconds
                if not strategy.trade_active:
                    print(f"⏱️  Elapsed: {elapsed}s | Trigger at 60s → {'READY' if elapsed >= 60 else 'WAITING'}")

                    if elapsed >= 60:
                        print("🔥 Triggering trade placement now...")
                        success = await strategy.place_put_credit_spread(session, account, price)
                        if success:
                            print("✅ Trade placement attempted!")
                        else:
                            print("⚠️ Placement returned False")

                strategy.print_trade_status()

            except Exception as e:
                print(f"Loop error: {e}")
                await asyncio.sleep(2)

            await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())