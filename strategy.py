import pandas as pd
from datetime import time

class OpeningRangeVWAPStrategy:
    def __init__(self):
        self.or_high = None
        self.or_low = None
        self.anchored_vwap = None
        self.traded_today = False

    def calculate_or_and_vwap(self, df: pd.DataFrame):
        df = df.rename(columns=str.lower).copy()
        
        # 15-minute Opening Range
        or_df = df.between_time('09:30', '09:45')
        if len(or_df) >= 3:
            self.or_high = float(or_df['high'].max())
            self.or_low = float(or_df['low'].min())
            print(f"✅ OR Set → High: {self.or_high:.2f} | Low: {self.or_low:.2f}")
        else:
            print("⚠️ Not enough data for Opening Range")

        # Anchored VWAP from 09:30
        vwap_df = df[df.index.time >= time(9, 30)]
        if len(vwap_df) > 5:
            tp = (vwap_df['high'] + vwap_df['low'] + vwap_df['close']) / 3
            self.anchored_vwap = (tp * vwap_df['volume']).cumsum() / vwap_df['volume'].cumsum()
            current_vwap = self.anchored_vwap.iloc[-1]
            print(f"✅ Anchored VWAP: {current_vwap:.2f}")
        else:
            print("⚠️ Not enough data for VWAP")

    def get_signal(self, current_price: float) -> dict:
        if self.or_high is None or self.or_low is None or self.anchored_vwap is None or self.traded_today:
            return {"action": "WAIT"}

        current_vwap = float(self.anchored_vwap.iloc[-1])
        
        # Debug prints as requested
        print(f"DEBUG → Current Price: {current_price:.2f} | VWAP: {current_vwap:.2f} | "
              f"OR High: {self.or_high:.2f} | OR Low: {self.or_low:.2f}")

        # ... rest of your signal logic unchanged
        if current_price > self.or_high + 2.0:
            direction = 'up'
        elif current_price < self.or_low - 2.0:
            direction = 'down'
        else:
            return {"action": "NO_BREAKOUT"}

        if abs(current_price - current_vwap) <= 8.0:
            self.traded_today = True
            if direction == 'up':
                return {"action": "SELL_PUT_SPREAD", "short_strike": round(self.or_low - 5)}
            else:
                return {"action": "SELL_CALL_SPREAD", "short_strike": round(self.or_high + 5)}
        return {"action": "WAITING_FOR_RETEST"}