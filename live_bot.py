import asyncio
from datetime import datetime
from tasty_session import TastySession
from strategy import OpeningRangeVWAPStrategy
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote
import sys
from threading import Thread
import queue

# Global queue for keyboard commands
command_queue = queue.Queue()

async def main():
    tasty = TastySession(is_test=True)
    session = tasty.login()
    await tasty.load_accounts()
    account = tasty.accounts[0]

    # Start keyboard listener in background thread
    Thread(target=keyboard_listener, daemon=True).start()
    
    # Start command processor
    asyncio.create_task(process_commands(strategy, session, account))

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

                # ... existing quote handling ...

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

def keyboard_listener():
    """Run in background thread to listen for keyboard input"""
    print("\n🔧 Keyboard Menu Active")
    print("   1  → Show current status")
    print("   2  → Force place a trade now")
    print("   3  → Manually close all positions")
    print("   9  → Exit bot gracefully\n")

    while True:
        try:
            cmd = input().strip()
            if cmd:
                command_queue.put(cmd)
        except:
            break

async def process_commands(strategy, session, account):
    """Process keyboard commands"""
    while True:
        try:
            if not command_queue.empty():
                cmd = command_queue.get_nowait()
                
                if cmd == "1":
                    print("📊 Manual status request...")
                    await strategy.print_detailed_status(session, account, 0)  # dummy price
                    
                elif cmd == "2":
                    print("🚀 Manual trade trigger...")
                    price = 0  # will use latest price logic inside method
                    await strategy.place_put_credit_spread(session, account, 7550)  # fallback price
                    
                elif cmd == "3":
                    print("🔴 Attempting to close all positions...")
                    # TODO: implement close all
                    
                elif cmd in ["9", "q", "exit"]:
                    print("🛑 Shutting down bot gracefully...")
                    # Cancel any open orders, etc.
                    sys.exit(0)
                    
                else:
                    print(f"Unknown command: {cmd}")
                    
        except Exception as e:
            print(f"Command error: {e}")
        
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
