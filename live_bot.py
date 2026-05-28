import asyncio
import sys
from threading import Thread
import queue
from datetime import datetime, timezone

from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote

command_queue = queue.Queue()

def keyboard_listener():
    print("\n🔧 === Keyboard Menu Active ===")
    print("   1 → Show detailed status")
    print("   2 → Force place a trade now")
    print("   9 → Exit bot gracefully\n")

    while True:
        try:
            cmd = input().strip()
            if cmd:
                command_queue.put(cmd)
        except:
            break


async def process_commands(strategy, session, account):
    while True:
        try:
            if not command_queue.empty():
                cmd = command_queue.get_nowait()
                if cmd == "1":
                    await strategy.print_detailed_status(session, account, 0)
                elif cmd == "2":
                    print("🚀 Forcing new trade...")
                    strategy.reset_trade_state()
                    await strategy.place_put_credit_spread(session, account, 7560)
                elif cmd in ["9", "q", "exit"]:
                    print("🛑 Exiting gracefully...")
                    sys.exit(0)
        except Exception as e:
            print(f"Command error: {e}")
        await asyncio.sleep(0.3)


async def main():
    tasty = TastySession(is_test=True)
    session = tasty.login()
    await tasty.load_accounts()
    account = tasty.accounts[0]
    print(f"Current Access Token: {session.session_token}")
    print(f"Expires At: {session.session_expiration}")
    dt = datetime.fromtimestamp(session.session_expiration, tz=timezone.utc)
    print(f"Expires: {dt}")

    strategy = OpeningRangeVWAPStrategy()
    print("🚀 SPX 0 DTE Bot - Tastytrade Sandbox")

    Thread(target=keyboard_listener, daemon=True).start()
    asyncio.create_task(process_commands(strategy, session, account))

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

                # Refresh session if needed
                if tasty.is_offline():
                    print("🔄 Refreshing session...")
                    session = tasty.login()

                if not strategy.trade_active and (datetime.now() - strategy.start_time).seconds >= 60:
                    await strategy.place_put_credit_spread(session, account, price)

                await strategy.check_for_fill_and_place_oco(session, account)
                await strategy.print_detailed_status(session, account, price)

            except Exception as e:
                print(f"Loop error: {e}")
                await asyncio.sleep(2)

            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())