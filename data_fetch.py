import pandas as pd
from datetime import datetime, timedelta
from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Candle
import asyncio

async def fetch_spx_bars_tasty(session, days_back=2, interval='5m'):
    """Fetch SPX candles via DXLink (sandbox works, though delayed)"""
    print(f"🔄 Fetching SPX {interval} bars (last {days_back} days)...")
    
    # Try these symbols one by one if one fails
    symbols_to_try = ["SPX", ".SPX", "/ES"]
    candle_symbol_base = None
    
    async with DXLinkStreamer(session) as streamer:
        df_list = []
        start_time = datetime.now() - timedelta(days=days_back)
        
        for sym in symbols_to_try:
            try:
                # Candle symbol format: "SPX{=5m}"
                candle_sym = f"{sym}{{={interval}}}"
                print(f"   Trying symbol: {candle_sym}")
                
                await streamer.subscribe(Candle, [candle_sym])
                
                print("📡 Subscribed — collecting candles...")
                
                # Collect a reasonable number of candles
                received = 0
                async for candle in streamer.listen(Candle):
                    received += 1
                    
                    dt = pd.to_datetime(candle.event_time, unit='ms').tz_localize(None)
                    
                    df_list.append({
                        'datetime': dt,
                        'open': float(candle.open),
                        'high': float(candle.high),
                        'low': float(candle.low),
                        'close': float(candle.close),
                        'volume': float(getattr(candle, 'volume', 0))
                    })
                    
                    if received % 30 == 0:
                        print(f"   Received {received} candles...")
                    
                    # Stop after we have enough recent data
                    if dt.date() >= start_time.date() and received > 80:
                        candle_symbol_base = sym
                        break
                        
                    if received > 300:  # safety
                        break
                
                if df_list:
                    break  # success with this symbol
                    
            except Exception as e:
                print(f"   Failed with {sym}: {e}")
                await asyncio.sleep(1)
                continue
    
    if not df_list:
        print("❌ No candles received from any symbol. We'll skip OR/VWAP for now.")
        return pd.DataFrame()
    
    df = pd.DataFrame(df_list)
    df.set_index('datetime', inplace=True)
    df = df.sort_index()
    
    print(f"✅ SUCCESS with symbol {candle_symbol_base} | Loaded {len(df)} bars")
    print(f"   Date range: {df.index[0]} → {df.index[-1]}")
    return df