import time
from datetime import datetime, timezone
from replay_engine import MarketReplayEngine

async def get_market_prices(force_refresh: bool = False):
    engine = MarketReplayEngine.get_instance()
    state = engine.get_state()
    
    now_iso = state.get("simulated_datetime_cot_iso") or state.get("simulated_datetime_iso", "")
    prices = state.get("prices", {})
    prices_usd = state.get("prices_usd_raw", {})
    variations = state.get("variations_24h", {})
    price_type = state.get("price_type", "OBSERVADO_REAL")

    result = {}
    for asset in ("BTC", "ETH", "USDT", "SOL"):
        result[asset] = {
            "asset": asset,
            "price_cop": prices.get(asset, 0.0),
            "price_usd_raw": prices_usd.get(asset, 0.0),
            "nature": price_type, # "OBSERVADO_REAL" o "CALCULADO_INTERPOLADO"
            "price_type": price_type,
            "change_24h": variations.get(asset, 0.0),
            "last_updated": now_iso,
            "last_updated_cot": now_iso,
            "source": "Market Replay Histórico 10-Nov-2026 (CoinGecko + TRM BanRep $3.269,88 COP/USD)"
        }

    return result

def get_current_replay_state():
    engine = MarketReplayEngine.get_instance()
    return engine.get_state()
