import pandas as pd
from datetime import datetime, time, timedelta
from collections import defaultdict
from decimal import Decimal

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
        self.oco_placed = False
        self.entry_credit = None
        self.entry_order_id = None
        self.start_time = datetime.now()
        self.last_status_print = None

    def update_with_price(self, price: float, volume: float = 1000.0):
        now = datetime.now()
        today_str = now.date().isoformat()

        if self.today != today_str:
            self.reset_for_new_day(today_str)

        minute_key = now.replace(second=0, microsecond=0)

        if minute_key not in self.minute_bars:
            self.minute_bars[minute_key] = {'open': price, 'high': price, 'low': price, 'close': price, 'volume': volume}
        else:
            bar = self.minute_bars[minute_key]
            bar['high'] = max(bar['high'], price)
            bar['low'] = min(bar['low'], price)
            bar['close'] = price
            bar['volume'] += volume

        # 15-min OR
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

    def reset_trade_state(self):
        """Reset so we can place another trade"""
        print("🔄 Resetting trade state (new trade allowed)")
        self.trade_active = False
        self.oco_placed = False
        self.entry_order_id = None
        self.entry_credit = None

    def get_signal(self, current_price: float) -> dict:
        if self.or_high is None or self.or_low is None or self.anchored_vwap is None or self.traded_today:
            return {"action": "WAIT"}

        print(f"DEBUG → Price: {current_price:.2f} | VWAP: {self.anchored_vwap:.2f} | OR H: {self.or_high:.2f} | OR L: {self.or_low:.2f}")

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

    # ==================== ORDER PLACEMENT ====================

    async def place_put_credit_spread(self, session, account, current_price: float):
        if self.trade_active:
            print("   ⏭️ Trade already active")
            return None

        print(f"\n🚀 [DEBUG] Attempting Put Credit Spread near {current_price:.1f}")

        try:
            for symbol in ["SPX", "/ES"]:
                print(f"   Trying symbol: {symbol}")
                chain = await get_option_chain(session, symbol)
                today = datetime.now().date()
                expirations = sorted([d for d in chain.keys() if d >= today])
                if not expirations:
                    continue
                exp_date = expirations[0]

                puts = [opt for opt in chain[exp_date] if opt.option_type == 'P']
                puts.sort(key=lambda x: x.strike_price)

                # Closer strike selection (better fill rate)
                target = Decimal(str(current_price - 10))   # ~10 points OTM
                short_opt = min(puts, key=lambda x: abs(x.strike_price - target))
                lower_puts = [p for p in puts if p.strike_price < short_opt.strike_price]
                if not lower_puts:
                    continue
                long_opt = max(lower_puts, key=lambda x: x.strike_price)

                width = float(short_opt.strike_price - long_opt.strike_price)
                print(f"   ✅ Spread → Short {short_opt.strike_price} | Long {long_opt.strike_price} | Width ${width}")

                short_leg = short_opt.build_leg(1, OrderAction.SELL_TO_OPEN)
                long_leg = long_opt.build_leg(1, OrderAction.BUY_TO_OPEN)

                mid = (float(getattr(short_opt, 'last_price', 1.0)) + float(getattr(long_opt, 'last_price', 0.5))) / 2
                credit = max(round(mid, 2), 0.50)

                order = NewOrder(
                    time_in_force=OrderTimeInForce.DAY,
                    order_type=OrderType.LIMIT,
                    legs=[short_leg, long_leg],
                    price=Decimal(str(-credit))
                )

                response = await account.place_order(session, order, dry_run=False)
                order_id = getattr(response, 'id', None) or getattr(getattr(response, 'order', None), 'id', None)

                print(f"✅ [LIVE] Order submitted | ID: {order_id} | Credit: ${credit}")

                self.trade_active = True
                self.entry_credit = credit
                self.entry_order_id = order_id
                return response

            print("❌ Could not build spread")
            return None

        except Exception as e:
            print(f"❌ Order failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def check_for_fill_and_place_oco(self, session, account):
        if not self.trade_active or self.oco_placed or not self.entry_order_id:
            return

        try:
            orders = await account.get_live_orders(session)
            for order in orders:
                if str(order.id) == str(self.entry_order_id):
                    print(f"   Order {order.id} → Status: {order.status}")
                    if hasattr(order, 'reject_reason') and order.reject_reason:
                        print(f"   ❌ Reject Reason: {order.reject_reason}")
                    if order.status in ["Filled", "PartiallyFilled"]:
                        print(f"🎉 ENTRY FILLED!")
                        await self.place_oco_orders(session, account)
                        self.oco_placed = True
                        return
        except Exception as e:
            print(f"Fill check error: {e}")

    async def place_oco_orders(self, session, account):
        if self.oco_placed:
            return
        print(f"🛡️ Placing OCO → TP ${self.entry_credit * 0.4:.2f} | SL ${self.entry_credit * 2.0:.2f}")

        try:
            positions = await account.get_positions(session)
            short_pos = next((p for p in positions if float(p.quantity) < 0), None)
            long_pos = next((p for p in positions if float(p.quantity) > 0), None)

            if not short_pos or not long_pos:
                print("❌ Could not find short/long legs")
                return

            short_close = short_pos.instrument.build_leg(1, OrderAction.SELL_TO_CLOSE)
            long_close = long_pos.instrument.build_leg(1, OrderAction.BUY_TO_CLOSE)

            tp_price = round(float(self.entry_credit) * 0.40, 2)
            sl_price = round(float(self.entry_credit) * 2.0, 2)

            oco = NewComplexOrder(
                orders=[
                    NewOrder(time_in_force=OrderTimeInForce.GTC, order_type=OrderType.LIMIT,
                             legs=[short_close, long_close], price=Decimal(str(-tp_price))),
                    NewOrder(time_in_force=OrderTimeInForce.GTC, order_type=OrderType.STOP,
                             legs=[short_close, long_close], stop_trigger=Decimal(str(sl_price)))
                ]
            )

            await account.place_complex_order(session, oco, dry_run=False)
            print(f"✅ OCO PLACED | TP ${tp_price} credit | SL ${sl_price} debit")
            self.oco_placed = True

        except Exception as e:
            print(f"❌ OCO failed: {e}")
            import traceback
            traceback.print_exc()

    async def print_detailed_status(self, session, account, current_price: float):
        now = datetime.now()
        if self.last_status_print is None or (now - self.last_status_print).seconds >= 120:
            try:
                positions = await account.get_positions(session)
                print(f"\n📊 [{now.strftime('%H:%M:%S')}] LIVE STATUS | SPX {current_price:.2f}")
                for pos in positions:
                    pnl = getattr(pos, 'realized_day_gain', 0) or getattr(pos, 'net_liquidating_value', 0)
                    print(f"   📍 {pos.symbol} | Qty: {pos.quantity} | P&L: ${pnl}")
                if self.trade_active:
                    print(f"   Bot Trade: ACTIVE | Credit: ${self.entry_credit} | OCO: {'✅' if self.oco_placed else '⏳'}")
            except Exception as e:
                print(f"Status error: {e}")
            self.last_status_print = now