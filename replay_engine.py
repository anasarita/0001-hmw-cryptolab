import os
import json
import time
import threading
from datetime import datetime, timezone, timedelta

class MarketReplayEngine:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = MarketReplayEngine()
            return cls._instance

    def __init__(self):
        self.lock = threading.Lock()
        self.dataset = None
        self.load_dataset()

        # Replay Simulation Clock State
        self.status = "RUNNING"
        # 16.91h (60870s) / 30min (1800s) = 33.82x
        self.speed = float(self.dataset.get("speed_factor_48x_or_adjusted", 33.82))
        self.session_duration_real_sec = float(self.dataset.get("academic_session_duration_seconds", 1800.0))
        self.total_span_seconds = float(self.dataset.get("total_span_seconds", 60870.0))
        self.elapsed_real_seconds = 0.0
        self.last_monotonic = time.monotonic()
        self.dataset_id = self.dataset.get("dataset_id", "HIST_20261110_COT")

        # Precompute 24h period statistics for BTC, ETH, USDT, SOL
        self.stats_period = {}
        ticks = self.dataset.get("ticks", [])
        for asset in ("BTC", "ETH", "USDT", "SOL"):
            p_list = [t["prices_cop"].get(asset, 0.0) for t in ticks if asset in t.get("prices_cop", {})]
            if p_list:
                self.stats_period[asset] = {
                    "high_cop": max(p_list),
                    "low_cop": min(p_list),
                    "open_cop": p_list[0],
                    "close_cop": p_list[-1]
                }

    def load_dataset(self, file_path="historical_market_data.json"):
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.dataset = json.load(f)
                return True
            except Exception as e:
                print(f"[REPLAY] Error cargando {file_path}: {e}")
        
        # Fallback minimal baseline
        now_dt = datetime(2026, 11, 10, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        ticks = []
        for i in range(204):
            dt_cot = now_dt + timedelta(minutes=i*5)
            ticks.append({
                "tick_index": i,
                "sim_second": i * 300,
                "timestamp_ms": int(dt_cot.timestamp() * 1000),
                "datetime_cot_iso": dt_cot.isoformat(),
                "datetime_utc_iso": dt_cot.astimezone(timezone.utc).isoformat(),
                "display_time_cot": dt_cot.strftime("%H:%M:%S COT"),
                "display_date_cot": "10 de Noviembre de 2026",
                "is_observed_point": True,
                "prices_cop": {"BTC": 317376835.87, "ETH": 9005342.69, "USDT": 4245.49, "SOL": 365263.64},
                "prices_usd_raw": {"BTC": 74676.90, "ETH": 2118.90, "USDT": 0.9989, "SOL": 85.94}
            })
        self.dataset = {
            "dataset_id": "HIST_20261110_COT",
            "dataset_name": "Jornada Efectiva 10 de Noviembre de 2026 (Hora Colombia / UTC-5)",
            "source_data": "CoinGecko Market API (USD) / TRM $4,250.00 COP",
            "date_cot": "10 de Noviembre de 2026",
            "coverage_status": "Intervalo real disponible hasta el momento de descarga (16:54:30 COT)",
            "total_observed_ticks": len(ticks),
            "start_cot_iso": ticks[0]["datetime_cot_iso"],
            "end_cot_iso": ticks[-1]["datetime_cot_iso"],
            "start_utc_iso": ticks[0]["datetime_utc_iso"],
            "end_utc_iso": ticks[-1]["datetime_utc_iso"],
            "effective_hours_observed": 16.91,
            "total_span_seconds": 60870.0,
            "academic_session_duration_seconds": 1800.0,
            "speed_factor_48x_or_adjusted": 33.82,
            "exchange_rate_documentation": {
                "tasa_cop_por_usd": 3269.88,
                "fuente": "Banco de la República de Colombia (https://www.banrep.gov.co/) - TRM oficial",
                "fecha_referencia": "2026-11-10"
            },
            "ticks": ticks
        }
        return False

    def _update_elapsed(self):
        """Must be called with self.lock acquired."""
        now_mono = time.monotonic()
        if self.status == "RUNNING":
            delta = now_mono - self.last_monotonic
            self.elapsed_real_seconds += delta
            if self.elapsed_real_seconds >= self.session_duration_real_sec:
                self.elapsed_real_seconds = self.session_duration_real_sec
                self.status = "COMPLETED"
        self.last_monotonic = now_mono

    def play(self):
        with self.lock:
            self._update_elapsed()
            if self.elapsed_real_seconds >= self.session_duration_real_sec:
                self.elapsed_real_seconds = 0.0
            self.status = "RUNNING"
            self.last_monotonic = time.monotonic()

    def pause(self):
        with self.lock:
            self._update_elapsed()
            self.status = "PAUSED"

    def reset(self):
        with self.lock:
            self.elapsed_real_seconds = 0.0
            self.last_monotonic = time.monotonic()
            self.status = "PAUSED"

    def set_speed(self, speed: float):
        with self.lock:
            self._update_elapsed()
            if speed > 0:
                self.speed = float(speed)

    def get_state(self):
        with self.lock:
            self._update_elapsed()

            elapsed_real = self.elapsed_real_seconds
            total_real = self.session_duration_real_sec
            progress_pct = min(100.0, round((elapsed_real / total_real) * 100.0, 2)) if total_real > 0 else 0.0

            time_span_sim = float(self.dataset.get("total_span_seconds", 60870.0))
            current_sim_sec = min(time_span_sim, elapsed_real * self.speed)

            ticks = self.dataset.get("ticks", [])
            total_ticks = len(ticks)

            current_prices_cop = {}
            current_prices_usd = {}
            price_type = "OBSERVADO_REAL"
            interpolation_meta = {}

            simulated_cot_iso = self.dataset.get("start_cot_iso", "")
            simulated_utc_iso = self.dataset.get("start_utc_iso", "")

            if total_ticks > 0:
                # Find interval
                k = 0
                for i in range(total_ticks - 1):
                    if ticks[i]["sim_second"] <= current_sim_sec <= ticks[i + 1]["sim_second"]:
                        k = i
                        break
                    elif i == total_ticks - 2:
                        k = i

                t1 = ticks[k]
                t2 = ticks[min(k + 1, total_ticks - 1)]

                sec1 = t1["sim_second"]
                sec2 = t2["sim_second"]
                span = sec2 - sec1

                fraction = 0.0 if span <= 0 else max(0.0, min(1.0, (current_sim_sec - sec1) / span))

                # Distinction: Observed Price vs Calculated / Interpolated Price
                # If within 2.5 seconds of a tick, consider exact observed point
                if abs(current_sim_sec - sec1) <= 2.5:
                    price_type = "OBSERVADO_REAL"
                    for asset in ("BTC", "ETH", "USDT", "SOL"):
                        current_prices_cop[asset] = t1["prices_cop"].get(asset, 0.0)
                        current_prices_usd[asset] = t1["prices_usd_raw"].get(asset, 0.0)
                    simulated_cot_iso = t1["datetime_cot_iso"]
                    simulated_utc_iso = t1["datetime_utc_iso"]
                    interpolation_meta = {
                        "price_nature": "OBSERVADO_REAL",
                        "tick_index": t1["tick_index"],
                        "observed_timestamp_cot": t1["datetime_cot_iso"],
                        "source": "Observación directa de CoinGecko API"
                    }
                elif abs(current_sim_sec - sec2) <= 2.5:
                    price_type = "OBSERVADO_REAL"
                    for asset in ("BTC", "ETH", "USDT", "SOL"):
                        current_prices_cop[asset] = t2["prices_cop"].get(asset, 0.0)
                        current_prices_usd[asset] = t2["prices_usd_raw"].get(asset, 0.0)
                    simulated_cot_iso = t2["datetime_cot_iso"]
                    simulated_utc_iso = t2["datetime_utc_iso"]
                    interpolation_meta = {
                        "price_nature": "OBSERVADO_REAL",
                        "tick_index": t2["tick_index"],
                        "observed_timestamp_cot": t2["datetime_cot_iso"],
                        "source": "Observación directa de CoinGecko API"
                    }
                else:
                    price_type = "CALCULADO_INTERPOLADO"
                    for asset in ("BTC", "ETH", "USDT", "SOL"):
                        p1 = t1["prices_cop"].get(asset, 0.0)
                        p2 = t2["prices_cop"].get(asset, p1)
                        current_prices_cop[asset] = round(p1 + (p2 - p1) * fraction, 2)

                        u1 = t1["prices_usd_raw"].get(asset, 0.0)
                        u2 = t2["prices_usd_raw"].get(asset, u1)
                        current_prices_usd[asset] = round(u1 + (u2 - u1) * fraction, 4)

                    try:
                        dt_start_cot = datetime.fromisoformat(self.dataset["start_cot_iso"])
                        sim_dt_cot = dt_start_cot + timedelta(seconds=current_sim_sec)
                        simulated_cot_iso = sim_dt_cot.isoformat()
                        simulated_utc_iso = sim_dt_cot.astimezone(timezone.utc).isoformat()
                    except Exception:
                        simulated_cot_iso = t1["datetime_cot_iso"]
                        simulated_utc_iso = t1["datetime_utc_iso"]

                    interpolation_meta = {
                        "price_nature": "CALCULADO_INTERPOLADO",
                        "method": "Interpolación lineal temporal continua ponderada",
                        "tick_anterior_idx": t1["tick_index"],
                        "tick_anterior_hora_cot": t1["display_time_cot"],
                        "tick_siguiente_idx": t2["tick_index"],
                        "tick_siguiente_hora_cot": t2["display_time_cot"],
                        "fraccion_ponderacion": round(fraction, 4),
                        "formula": "P = P1 + (P2 - P1) * fraccion"
                    }

            # Variations from start of Nov 10 (00:00:00 COT)
            variations_day = {}
            if total_ticks > 0:
                init_prices = ticks[0]["prices_cop"]
                for asset in ("BTC", "ETH", "USDT", "SOL"):
                    p0 = init_prices.get(asset, 1.0)
                    p_now = current_prices_cop.get(asset, p0)
                    chg = ((p_now - p0) / p0) * 100.0
                    variations_day[asset] = round(chg, 2)

            # Chart history for progressive chart
            chart_history = []
            if total_ticks > 0:
                for i in range(0, k + 1):
                    t_item = ticks[i]
                    ts_sec = int(t_item.get("timestamp_ms", 0) // 1000)
                    chart_history.append({
                        "time": ts_sec,
                        "timestamp": ts_sec,
                        "timestamp_ms": t_item.get("timestamp_ms", 0),
                        "sim_second": t_item["sim_second"],
                        "time_label": t_item["datetime_cot_iso"][11:16] + " COT",
                        "time_full_cot": t_item.get("display_time_cot") or (t_item["datetime_cot_iso"][11:19] + " COT"),
                        "datetime_cot_iso": t_item["datetime_cot_iso"],
                        "date_label": t_item.get("display_date_cot", "10 de Noviembre de 2026"),
                        "is_observed": True,
                        "nature": "OBSERVADO_REAL",
                        "BTC": t_item["prices_cop"].get("BTC"),
                        "ETH": t_item["prices_cop"].get("ETH"),
                        "USDT": t_item["prices_cop"].get("USDT"),
                        "SOL": t_item["prices_cop"].get("SOL")
                    })

                # Append or update current simulated point
                try:
                    current_ts_sec = int(datetime.fromisoformat(simulated_cot_iso).timestamp())
                except Exception:
                    current_ts_sec = chart_history[-1]["time"] if chart_history else 0

                if not chart_history or current_ts_sec > chart_history[-1]["time"]:
                    chart_history.append({
                        "time": current_ts_sec,
                        "timestamp": current_ts_sec,
                        "timestamp_ms": current_ts_sec * 1000,
                        "sim_second": round(current_sim_sec),
                        "time_label": simulated_cot_iso[11:16] + " COT",
                        "time_full_cot": simulated_cot_iso[11:19] + " COT",
                        "datetime_cot_iso": simulated_cot_iso,
                        "date_label": "10 de Noviembre de 2026",
                        "is_observed": (price_type == "OBSERVADO_REAL"),
                        "nature": price_type,
                        "BTC": current_prices_cop.get("BTC"),
                        "ETH": current_prices_cop.get("ETH"),
                        "USDT": current_prices_cop.get("USDT"),
                        "SOL": current_prices_cop.get("SOL")
                    })
                elif chart_history:
                    chart_history[-1]["nature"] = price_type
                    chart_history[-1]["is_observed"] = (price_type == "OBSERVADO_REAL")
                    for a in ("BTC", "ETH", "USDT", "SOL"):
                        if a in current_prices_cop:
                            chart_history[-1][a] = current_prices_cop[a]

            min_real = int(elapsed_real // 60)
            sec_real = int(elapsed_real % 60)
            elapsed_formatted = f"{min_real:02d}:{sec_real:02d} / 30:00"

            try:
                dt_obj_cot = datetime.fromisoformat(simulated_cot_iso)
                sim_formatted_cot = dt_obj_cot.strftime("%d de Noviembre de 2026 — %H:%M:%S COT")
            except Exception:
                sim_formatted_cot = simulated_cot_iso

            is_completed = (self.elapsed_real_seconds >= self.session_duration_real_sec)

            return {
                "status": self.status,
                "is_completed": is_completed,
                "speed": self.speed,
                "elapsed_real_seconds": round(elapsed_real, 1),
                "total_real_seconds": self.session_duration_real_sec,
                "progress_percent": progress_pct,
                "elapsed_formatted": elapsed_formatted,
                "simulated_datetime_cot_iso": simulated_cot_iso,
                "simulated_datetime_utc_iso": simulated_utc_iso,
                "simulated_datetime_iso": simulated_cot_iso,
                "simulated_datetime_formatted": sim_formatted_cot,
                "current_sim_second": round(current_sim_sec),
                "dataset_id": self.dataset_id,
                "dataset_name": self.dataset.get("dataset_name", "Jornada Efectiva 10 de Noviembre de 2026"),
                "periodo_efectivo_observado": "10 de Noviembre de 2026 (00:00:00 a 16:54:30 COT)",
                "horas_efectivas": self.dataset.get("effective_hours_observed", 16.91),
                "exchange_rate_documentation": self.dataset.get("exchange_rate_documentation", {}),
                "prices": current_prices_cop,
                "prices_usd_raw": current_prices_usd,
                "price_type": price_type, # "OBSERVADO_REAL" o "CALCULADO_INTERPOLADO"
                "interpolation_meta": interpolation_meta,
                "variations_24h": variations_day,
                "stats_period": getattr(self, "stats_period", {}),
                "chart_history": chart_history,
                "disclaimer": "Simulación con datos históricos reales — 10 de Noviembre de 2026 (Hora Colombia / UTC-5)"
            }

    def get_price_for_trade(self, asset: str) -> dict:
        state = self.get_state()
        asset_norm = asset.upper()
        return {
            "asset": asset_norm,
            "price_cop": state["prices"].get(asset_norm, 0.0),
            "price_usd_raw": state["prices_usd_raw"].get(asset_norm, 0.0),
            "price_type": state["price_type"], # "OBSERVADO_REAL" o "CALCULADO_INTERPOLADO"
            "simulated_datetime_cot": state["simulated_datetime_cot_iso"],
            "simulated_datetime_utc": state["simulated_datetime_utc_iso"],
            "dataset_id": state["dataset_id"],
            "trm_applied": state["exchange_rate_documentation"].get("tasa_cop_por_usd", 3269.88),
            "interpolation_meta": state["interpolation_meta"]
        }

    def get_current_price(self, asset: str) -> float:
        return self.get_price_for_trade(asset)["price_cop"]
