import pandas as pd
from datetime import datetime, time, timedelta
from collections import defaultdict
from decimal import Decimal

# Tastytrade imports
from tastytrade.order import NewOrder, NewComplexOrder, OrderAction, OrderType, OrderTimeInForce
from tastytrade.instruments import get_option_chain


class OpeningRangeVWAPStrategy:
    def __init__(self):
        self.minute_bars = defaultdict(dict)
        self.or_high = None
        self.or_low = None
        self.anchored_vwap = None
        self.traded_today = False
        self.today = None
        self.last_vwap_print = None
        
        # Trade management
        self.trade_active = False
        self.entry_credit = None
        self.start_time = datetime.now()
        self.last_status_print = None

    def update_with_price(self, price: float, volume: float = 1000.0):
        """Build 1-minute bars + calculate OR & VWAP"""
        now = datetime.now()
        today_str = now.date().isoformat()

        if self.today != today_str:
            self.reset_for_new_day(today_str)

        minute_key = now.replace(second=0, microsecond=0)

        if minute_key not in self.minute_bars:
            self.minute_bars[minute_key] = {
                'open': price, 'high': price, 'low': price, 'close': price, 'volume': volume
            }
        else:
            bar = self.minute_bars[minute_key]
            bar['high'] = max(bar['high'], price)
            bar['low'] = min(bar['low'], price)
            bar['close'] = price
            bar['volume'] += volume

        # 15-min Opening Range
        if self.or_high is None and now.time() >= time(9, 45):
            or_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            or_end = now.replace(hour=9, minute=45, second=0, microsecond=0)
            or_bars = [b for k, b in self.minute_bars.items() if or_start <= k <= or_end]
            if or_bars:
                self.or_high = max(b['high'] for b in or_bars)
                self.or_low = min(b['low'] for b in or_bars)
                print(f"✅ 15min OR → High: {self.or_high:.2f} | Low: {self.or_low:.2f}")

        # Anchored VWAP
        if now.time() >= time(9, 30):
            vwap_bars = [b for k, b in self.minute_bars.items() if k.time() >= time(9, 30)]
            if len(vwap_bars) > 3:
                df = pd.DataFrame(vwap_bars)
                tp = (df['high'] + df['low'] + df['close']) / 3
                vwap = (tp * df['volume']).cumsum() / df['volume'].cumsum()
                self.anchored_vwap = float(vwap.iloc[-1])

                if self.last_vwap_print is None or (now - self.last_vwap_print).seconds >= 15:
                    print(f"✅ Current VWAP: {self.anchored_vwap:.2f} ({len(vwap_bars)} min bars)")
                    self.last_vwap_print = now

    def reset_for_new_day(self, today_str):
        print(f"🔄 New trading day: {today_str}")
        self.minute_bars.clear()
        self.or_high = self.or_low = self.anchored_vwap = None
        self.traded_today = False
        self.today = today_str
        self.last_vwap_print = None

    def get_signal(self, current_price: float) -> dict:
        if self.or_high is None or self.or_low is None or self.anchored_vwap is None or self.traded_today:
            return {"action": "WAIT"}

        print(f"DEBUG → Price: {current_price:.2f} | VWAP: {self.anchored_vwap:.2f} | "
              f"OR H: {self.or_high:.2f} | OR L: {self.or_low:.2f}")

        if current_price > self.or_high + 2:
            direction = 'up'
        elif current_price < self.or_low - 2:
            direction = 'down'
        else:
            return {"action": "NO_BREAKOUT"}

        if abs(current_price - self.anchored_vwap) <= 8:
            self.traded_today = True
            return {"action": "SELL_PUT_SPREAD" if direction == 'up' else "SELL_CALL_SPREAD"}
        return {"action": "WAITING_FOR_RETEST"}

    async def place_put_credit_spread(self, session, account, current_price: float):
        """Flexible spread: uses smallest available width (even if wide)"""
        if self.trade_active or (datetime.now() - self.start_time).seconds < 60:
            return False

        print(f"\n🚀 [SANDBOX] Attempting Put Credit Spread near {current_price:.1f}")

        try:
            for symbol in ["SPX", "/ES"]:   # Try SPX then futures options
                print(f"   Trying symbol: {symbol}")
                chain = await get_option_chain(session, symbol)
                
                today = datetime.now().date()
                expirations = sorted([d for d in chain.keys() if d >= today])
                if not expirations:
                    continue
                    
                exp_date = expirations[0]
                puts = [opt for opt in chain[exp_date] if opt.option_type == 'P']
                puts.sort(key=lambda x: x.strike_price)

                print(f"   Found {len(puts)} put strikes for {symbol} exp {exp_date}")

                # Debug: Show all strikes
                print("   All available put strikes:")
                for p in puts:
                    print(f"     {p.strike_price}")

                if len(puts) < 2:
                    print(f"   Not enough strikes for {symbol}")
                    continue

                # Pick short strike ~20 points OTM
                target = Decimal(str(current_price - 20))
                short_opt = min(puts, key=lambda x: abs(x.strike_price - target))
                print(f"   Selected Short Strike: {short_opt.strike_price}")

                # Find the closest lower strike (any width)
                lower_puts = [p for p in puts if p.strike_price < short_opt.strike_price]
                if not lower_puts:
                    print("   No lower strikes available")
                    continue

                long_opt = max(lower_puts, key=lambda x: x.strike_price)  # closest below short
                width = float(short_opt.strike_price - long_opt.strike_price)
                print(f"   ✅ Found spread → Short {short_opt.strike_price} | Long {long_opt.strike_price} | Width: ${width}")

                # Build and place order
                short_leg = short_opt.build_leg(1, OrderAction.SELL_TO_OPEN)
                long_leg = long_opt.build_leg(1, OrderAction.BUY_TO_OPEN)

                mid = (float(getattr(short_opt, 'last_price', 1.0)) + float(getattr(long_opt, 'last_price', 0.5))) / 2
                credit = max(round(mid, 2), 0.40)

                order = NewOrder(
                    time_in_force=OrderTimeInForce.DAY,
                    order_type=OrderType.LIMIT,
                    legs=[short_leg, long_leg],
                    price=Decimal(str(-credit))
                )

                response = await account.place_order(session, order, dry_run=False)
                print(f"✅ [DRY RUN] {width:.0f}-wide Put Credit Spread on {symbol} | Credit ≈ ${credit}")

                self.trade_active = True
                self.entry_credit = credit
                return True

            print("❌ Could not build any spread on SPX or /ES")
            return False

        except Exception as e:
            print(f"❌ Order failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_trade_status(self):
        now = datetime.now()
        if self.last_status_print is None or (now - self.last_status_print).seconds >= 120:
            seconds_left = max(0, 60 - (now - self.start_time).seconds)
            status = "ACTIVE" if self.trade_active else f"PENDING ({seconds_left}s left)"
            print(f"📊 [{now.strftime('%H:%M:%S')}] STATUS: {status} | Credit: {self.entry_credit}")
            self.last_status_print = now