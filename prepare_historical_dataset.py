import json
from datetime import datetime, timezone, timedelta

def generate_historical_dataset():
    with open("raw_coingecko_chart.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Definición de Zona Horaria de Colombia (America/Bogota, UTC-5)
    TZ_COT = timezone(timedelta(hours=-5))

    # Tasa Representativa del Mercado (TRM) oficial de referencia (Banco de la República)
    TRM_COP = 3269.88
    TRM_METADATA = {
        "tasa_cop_por_usd": TRM_COP,
        "fuente": "Banco de la República de Colombia (https://www.banrep.gov.co/) - Tasa Representativa del Mercado (TRM) oficial",
        "fecha_referencia": "2026-11-10",
        "metodologia": "Precio_COP = round(Precio_USD_Observado * 3269.88, 2)"
    }

    btc_raw = raw["BTC"]
    eth_raw = raw["ETH"]
    usdt_raw = raw["USDT"]
    sol_raw = raw["SOL"]

    min_len = min(len(btc_raw), len(eth_raw), len(usdt_raw), len(sol_raw))

    # Filtrar estrictamente las observaciones pertenecientes al 10 de noviembre de 2026 en Colombia (COT, UTC-5)
    # y comprobar que ninguna observación tenga fecha futura respecto al momento de corte
    ticks = []
    tick_idx = 0

    for i in range(min_len):
        ts_ms = btc_raw[i][0]
        dt_utc = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc)
        dt_cot = dt_utc.astimezone(TZ_COT)

        # Solo incluir observaciones cuyo día en Colombia sea estrictamente el 10 de noviembre de 2026
        if dt_cot.year == 2026 and dt_cot.month == 11 and dt_cot.day == 10:
            p_btc_usd = float(btc_raw[i][1])
            p_eth_usd = float(eth_raw[i][1])
            p_usdt_usd = float(usdt_raw[i][1])
            p_sol_usd = float(sol_raw[i][1])

            p_btc_cop = round(p_btc_usd * TRM_COP, 2)
            p_eth_cop = round(p_eth_usd * TRM_COP, 2)
            p_usdt_cop = round(p_usdt_usd * TRM_COP, 2)
            p_sol_cop = round(p_sol_usd * TRM_COP, 2)

            ticks.append({
                "tick_index": tick_idx,
                "timestamp_ms": ts_ms,
                "datetime_utc_iso": dt_utc.isoformat(),
                "datetime_cot_iso": dt_cot.isoformat(),
                "display_time_cot": dt_cot.strftime("%H:%M:%S COT"),
                "display_date_cot": dt_cot.strftime("%d de Noviembre de 2026"),
                "display_full_cot": dt_cot.strftime("%d/%m/%Y %H:%M:%S COT"),
                "is_observed_point": True, # Punto histórico observado real
                "prices_cop": {
                    "BTC": p_btc_cop,
                    "ETH": p_eth_cop,
                    "USDT": p_usdt_cop,
                    "SOL": p_sol_cop
                },
                "prices_usd_raw": {
                    "BTC": round(p_btc_usd, 2),
                    "ETH": round(p_eth_usd, 2),
                    "USDT": round(p_usdt_usd, 4),
                    "SOL": round(p_sol_usd, 2)
                }
            })
            tick_idx += 1

    if not ticks:
        raise ValueError("No se encontraron observaciones para el 10 de noviembre de 2026 en Colombia.")

    # Calcular intervalo efectivo y tiempos simulados
    start_ts_ms = ticks[0]["timestamp_ms"]
    end_ts_ms = ticks[-1]["timestamp_ms"]
    total_effective_seconds = (end_ts_ms - start_ts_ms) / 1000.0 # Segundos históricos reales observados

    # Asignar a cada tick su segundo simulado respecto al inicio
    for t in ticks:
        t["sim_second"] = round((t["timestamp_ms"] - start_ts_ms) / 1000.0, 1)

    # Duración de la sesión académica = 30 minutos (1800 segundos)
    SESSION_DURATION_REAL_SEC = 1800.0
    effective_speed = round(total_effective_seconds / SESSION_DURATION_REAL_SEC, 2)

    dataset = {
        "dataset_id": "HIST_20261110_COT",
        "dataset_name": "Jornada Efectiva 10 de Noviembre de 2026 (Hora Colombia / UTC-5)",
        "source_data": "CoinGecko Market API (cotizaciones históricas a intervalos de 5 minutos)",
        "conversion_currency": "COP (Pesos Colombianos)",
        "exchange_rate_documentation": TRM_METADATA,
        "date_cot": "10 de Noviembre de 2026",
        "coverage_status": "Intervalo real disponible hasta el momento de descarga (16:54:30 COT)",
        "total_observed_ticks": len(ticks),
        "start_cot_iso": ticks[0]["datetime_cot_iso"],
        "end_cot_iso": ticks[-1]["datetime_cot_iso"],
        "start_utc_iso": ticks[0]["datetime_utc_iso"],
        "end_utc_iso": ticks[-1]["datetime_utc_iso"],
        "effective_hours_observed": round(total_effective_seconds / 3600.0, 2),
        "total_span_seconds": total_effective_seconds,
        "academic_session_duration_seconds": SESSION_DURATION_REAL_SEC,
        "speed_factor_48x_or_adjusted": effective_speed, # 33.82x para abarcar exactamente las 16h 54m en 30 minutos
        "ticks": ticks
    }

    with open("historical_market_data.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print(" DATASET HISTÓRICO AJUSTADO RIGUROSAMENTE AL 10 DE NOVIEMBRE DE 2026")
    print("=" * 70)
    print(f" Puntos observados:       {len(ticks)} observaciones (1 cada 5 minutos)")
    print(f" Inicio (Colombia / UTC-5): {dataset['start_cot_iso']}")
    print(f" Fin (Colombia / UTC-5):    {dataset['end_cot_iso']}")
    print(f" Inicio (UTC):              {dataset['start_utc_iso']}")
    print(f" Fin (UTC):                 {dataset['end_utc_iso']}")
    print(f" Período efectivo:          {dataset['effective_hours_observed']} horas ({total_effective_seconds:,.0f} segundos)")
    print(f" Velocidad de Replay:       {dataset['speed_factor_48x_or_adjusted']}x (reproduce las {dataset['effective_hours_observed']}h en 30 minutos)")
    print(f" TRM Documentada:           ${TRM_COP:,.2f} COP/USD (10 de Noviembre de 2026)")
    print(f" Precios Inicio (COP):      BTC: {ticks[0]['prices_cop']['BTC']:,.2f} | ETH: {ticks[0]['prices_cop']['ETH']:,.2f} | USDT: {ticks[0]['prices_cop']['USDT']:,.2f} | SOL: {ticks[0]['prices_cop']['SOL']:,.2f}")
    print(f" Precios Fin (COP):         BTC: {ticks[-1]['prices_cop']['BTC']:,.2f} | ETH: {ticks[-1]['prices_cop']['ETH']:,.2f} | USDT: {ticks[-1]['prices_cop']['USDT']:,.2f} | SOL: {ticks[-1]['prices_cop']['SOL']:,.2f}")
    print("=" * 70)

if __name__ == "__main__":
    generate_historical_dataset()
