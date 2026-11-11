import os
import sys
import json
import time
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    httpx = None

from prepare_historical_dataset import generate_historical_dataset

def download_historical_data():
    print("=" * 68)
    print(" CRYPTO LAB — DESCARGADOR DE DATOS HISTÓRICOS REALES (D-015)")
    print("=" * 68)
    print(" Intentando consultar cotizaciones de las últimas 24 horas...")

    if httpx is None:
        print("[!] httpx no está instalado. Utilizando conjunto histórico precargado.")
        return

    coins = [('bitcoin', 'BTC'), ('ethereum', 'ETH'), ('tether', 'USDT'), ('solana', 'SOL')]
    headers = {'User-Agent': 'CryptoLab-Historical-Downloader/1.0'}
    downloaded = {}

    success_all = True
    for cid, sym in coins:
        print(f" -> Descargando serie de {sym}...", end="", flush=True)
        coin_success = False
        for attempt in range(3):
            try:
                r = httpx.get(
                    f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=usd&days=1",
                    headers=headers,
                    timeout=12.0
                )
                if r.status_code == 200:
                    pts = r.json().get('prices', [])
                    if len(pts) >= 100:
                        downloaded[sym] = pts
                        coin_success = True
                        print(f" [OK] {len(pts)} puntos recibidos.")
                        break
                elif r.status_code == 429:
                    time.sleep(5.0)
            except Exception:
                time.sleep(2.0)
        
        if not coin_success:
            print(" [FALLO DE CONEXIÓN O LÍMITE API]")
            success_all = False
        time.sleep(2.5)

    if success_all and len(downloaded) == 4:
        with open("raw_coingecko_chart.json", "w", encoding="utf-8") as f:
            json.dump(downloaded, f)
        generate_historical_dataset()
        print("\n[ÉXITO] Nuevos datos históricos descargados y procesados correctamente.")
    else:
        print("\n[AVISO] No fue posible descargar todas las monedas debido a límites de API o red.")
        if os.path.exists("historical_market_data.json"):
            print("[INFO] Se conserva y activa el conjunto histórico oficial precargado:")
            print("       'Jornada Real 10 de Noviembre de 2026 (24 Horas)'.")
            print("       Tu simulador funcionará perfectamente sin conexión externa.")
        else:
            print("[ERROR] No se encontró conjunto de respaldo.")

    print("=" * 68)

if __name__ == "__main__":
    download_historical_data()
