import pandas as pd
from datetime import datetime, time
from collections import defaultdict

class OpeningRangeVWAPStrategy:
    def __init__(self):
        self.minute_bars = defaultdict(dict)  # key: (date, minute_timestamp)
        self.or_high = None
        self.or_low = None
        self.anchored_vwap = None
        self.traded_today = False
        self.today = None
        self.last_vwap_print = None

    def update_with_price(self, price: float, volume: float = 1000.0):
        now = datetime.now()
        today_str = now.date().isoformat()

        if self.today != today_str:
            self.reset_for_new_day(today_str)

        # Create minute-level bar key (e.g., 09:31:00)
        minute_key = now.replace(second=0, microsecond=0)

        if minute_key not in self.minute_bars:
            self.minute_bars[minute_key] = {
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
        else:
            bar = self.minute_bars[minute_key]
            bar['high'] = max(bar['high'], price)
            bar['low'] = min(bar['low'], price)
            bar['close'] = price
            bar['volume'] += volume

        # Calculate 15-min Opening Range after 09:45
        if self.or_high is None and now.time() >= time(9, 45):
            or_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            or_end = now.replace(hour=9, minute=45, second=0, microsecond=0)
            
            or_bars = [b for k, b in self.minute_bars.items() 
                      if or_start <= k <= or_end]
            
            if or_bars:
                self.or_high = max(b['high'] for b in or_bars)
                self.or_low = min(b['low'] for b in or_bars)
                print(f"✅ 15min OR Calculated → High: {self.or_high:.2f} | Low: {self.or_low:.2f}")

        # Update Anchored VWAP (from 09:30 onward) — only print every 10-15 seconds
        if now.time() >= time(9, 30):
            vwap_bars = [b for k, b in self.minute_bars.items() 
                        if k.time() >= time(9, 30)]
            
            if len(vwap_bars) > 3:
                df = pd.DataFrame(vwap_bars)
                tp = (df['high'] + df['low'] + df['close']) / 3
                vwap = (tp * df['volume']).cumsum() / df['volume'].cumsum()
                self.anchored_vwap = float(vwap.iloc[-1])

                # Throttle prints
                if self.last_vwap_print is None or (now - self.last_vwap_print).seconds >= 15:
                    print(f"✅ Current VWAP: {self.anchored_vwap:.2f} ({len(vwap_bars)} min bars)")
                    self.last_vwap_print = now

    def reset_for_new_day(self, today_str):
        print(f"🔄 New trading day detected: {today_str}")
        self.minute_bars.clear()
        self.or_high = None
        self.or_low = None
        self.anchored_vwap = None
        self.traded_today = False
        self.today = today_str
        self.last_vwap_print = None

    def get_signal(self, current_price: float) -> dict:
        if self.or_high is None or self.or_low is None or self.anchored_vwap is None or self.traded_today:
            return {"action": "WAIT"}

        print(f"DEBUG → Current Price: {current_price:.2f} | VWAP: {self.anchored_vwap:.2f} | "
              f"OR High: {self.or_high:.2f} | OR Low: {self.or_low:.2f}")

        # ... your existing signal logic here ...
        if current_price > self.or_high + 2.0:
            direction = 'up'
        elif current_price < self.or_low - 2.0:
            direction = 'down'
        else:
            return {"action": "NO_BREAKOUT"}

        if abs(current_price - self.anchored_vwap) <= 8.0:
            self.traded_today = True
            return {"action": "SELL_PUT_SPREAD" if direction == 'up' else "SELL_CALL_SPREAD"}

        return {"action": "WAITING_FOR_RETEST"}