import os
import sys
import unittest
import time
import json
import uuid
from decimal import Decimal

# Ensure utf-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from starlette.testclient import TestClient
from database import init_db, get_admin_credentials
from server import app
from replay_engine import MarketReplayEngine

client = None

class TestMarketReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global client
        cls.orig_db = os.environ.get("CRYPTOLAB_DB")
        cls.test_db = f"temp_test_replay_{uuid.uuid4().hex[:6]}.db"
        os.environ["CRYPTOLAB_DB"] = cls.test_db
        init_db(cls.test_db)
        client = TestClient(app)
        cls.engine = MarketReplayEngine.get_instance()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass
        if cls.orig_db:
            os.environ["CRYPTOLAB_DB"] = cls.orig_db
        else:
            os.environ.pop("CRYPTOLAB_DB", None)

    def test_replay_clock_and_pricing(self):
        print("\n" + "=" * 65)
        print(" EJECUTANDO PRUEBAS DEL MOTOR MARKET REPLAY (D-015 CORREGIDO)")
        print("=" * 65)

        # 1. Authentic Dataset verification (No future dates, Colombian window Nov 10)
        state0 = self.engine.get_state()
        self.assertEqual(state0["dataset_id"], "HIST_20261110_COT")
        self.assertIn("10 de Noviembre de 2026", state0["dataset_name"])
        self.assertEqual(state0["periodo_efectivo_observado"], "10 de Noviembre de 2026 (00:00:00 a 16:54:30 COT)")
        self.assertAlmostEqual(state0["horas_efectivas"], 16.91, places=1)

        # Verify TRM documentation (Banco de la República)
        trm_doc = state0["exchange_rate_documentation"]
        self.assertEqual(trm_doc["tasa_cop_por_usd"], 3269.88)
        self.assertIn("Banco de la República", trm_doc["fuente"])
        print(f"[OK] TRM Oficial Documentada: COP {trm_doc['tasa_cop_por_usd']:,.2f} ({trm_doc['fuente']})")

        # Verify Clock Start matches Nov 10 Colombia Time (COT = UTC-5)
        self.engine.reset()
        st_reset = self.engine.get_state()
        self.assertIn("00:00:00", st_reset["simulated_datetime_cot_iso"])
        self.assertIn("05:00:00", st_reset["simulated_datetime_utc_iso"]) # 00:00 COT is 05:00 UTC
        print(f"[OK] Reloj inicia exactamente el 10-Nov-2026 a las 00:00:00 COT (05:00:00 UTC).")

        # 2. Distinguish Observed Real vs Calculated Interpolated
        self.assertEqual(st_reset["price_type"], "OBSERVADO_REAL")
        print(f"[OK] Tipo de precio al inicio: {st_reset['price_type']} (Tick exacto CoinGecko)")

        # Verify assets and realistic prices
        self.assertIn("BTC", st_reset["prices"])
        self.assertIn("ETH", st_reset["prices"])
        self.assertIn("USDT", st_reset["prices"])
        self.assertIn("SOL", st_reset["prices"])
        self.assertGreater(st_reset["prices"]["BTC"], 200000000.0)
        self.assertGreater(st_reset["prices"]["USDT"], 3000.0)
        self.assertLess(st_reset["prices"]["USDT"], 3500.0)
        print(f"[OK] Precios verificados: BTC: COP {st_reset['prices']['BTC']:,.2f} | USDT: COP {st_reset['prices']['USDT']:,.2f}")

        # 3. Clock advancement at effective classroom speed
        self.engine.play()
        time.sleep(1.0)
        state1 = self.engine.get_state()
        self.assertEqual(state1["status"], "RUNNING")
        self.assertGreater(state1["elapsed_real_seconds"], 0.8)
        self.assertGreater(state1["current_sim_second"], 20)
        print(f"[OK] Reloj avanzó a velocidad efectiva {state1['speed']}x ({state1['current_sim_second']}s simulados).")
        print(f"     Hora simulada actual: {state1['simulated_datetime_formatted']}")

        # 4. Synchronized Server Endpoint Check
        resp = client.get("/api/market/replay-status")
        self.assertEqual(resp.status_code, 200)
        api_state = resp.json()
        self.assertEqual(api_state["status"], "RUNNING")
        self.assertEqual(api_state["dataset_id"], "HIST_20261110_COT")
        self.assertIn("chart_history", api_state)
        print(f"[OK] Endpoint /api/market/replay-status responde sincronizado ({len(api_state['chart_history'])} puntos).")

        # 5. Admin Controls with Secure Credentials (.env)
        admin_u, admin_p = get_admin_credentials()
        login_res = client.post("/api/admin/login", json={"username": admin_u, "password": admin_p})
        self.assertEqual(login_res.status_code, 200, "Login administrativo con credenciales de .env debe ser exitoso.")
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Verify old admin/admin123 fails
        bad_login = client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(bad_login.status_code, 401, "admin123 predeterminado debe ser rechazado.")
        print("[OK] Credenciales administrativas seguras validadas; acceso por defecto bloqueado.")

        # Pause
        p_res = client.post("/api/admin/replay/pause", headers=headers)
        self.assertEqual(p_res.status_code, 200)
        self.assertEqual(p_res.json()["state"]["status"], "PAUSED")
        
        # Check that paused prices do not change
        price_paused_1 = self.engine.get_current_price("BTC")
        time.sleep(0.4)
        price_paused_2 = self.engine.get_current_price("BTC")
        self.assertEqual(price_paused_1, price_paused_2)
        print("[OK] Pausa verificada: las cotizaciones se congelan con precisión.")

        # Reanudar
        play_res = client.post("/api/admin/replay/play", headers=headers)
        self.assertEqual(play_res.status_code, 200)
        self.assertEqual(play_res.json()["state"]["status"], "RUNNING")
        print("[OK] Reanudación del reloj verificada.")

        # 6. Financial Trade with Replay Price & Auditable Metadata
        room_code = f"REP{uuid.uuid4().hex[:4].upper()}"
        client.post("/api/admin/rooms", json={"code": room_code, "name": "Sala Replay", "initial_bank_balance_cop": 50000000}, headers=headers)

        # Participant joins
        p_res = client.post("/api/rooms/join", json={"room_code": room_code, "alias": "TRADER_REPLAY"})
        p_token = p_res.json()["token"]
        p_headers = {"Authorization": f"Bearer {p_token}"}

        # Move COP from bank to wallet
        client.post("/api/participant/bank-transfer", json={"action": "DEPOSIT", "amount": 20000000}, headers=p_headers)

        # Execute BUY order
        exp_price = self.engine.get_current_price("USDT")
        trade_res = client.post("/api/participant/trade", json={"side": "BUY", "asset": "USDT", "amount": 2000, "quote_type": "CRYPTO"}, headers=p_headers)
        self.assertEqual(trade_res.status_code, 200)
        trade_data = trade_res.json()

        # Check unit price and commission
        self.assertAlmostEqual(trade_data["unit_price_cop"], exp_price, places=1)
        self.assertEqual(trade_data["fee_cop"], round(trade_data["gross_amount_cop"] * 0.002, 2))
        print(f"[OK] Compra ejecutada a tasa de backend: 2000 USDT @ COP {trade_data['unit_price_cop']:,.2f} (+ fee COP {trade_data['fee_cop']:,.2f}).")

        # Verify transaction record metadata
        history_res = client.get("/api/participant/history", headers=p_headers)
        txs = history_res.json()["transactions"]
        buy_tx = next(t for t in txs if t["tx_type"] == "BUY_CRYPTO")
        meta = json.loads(buy_tx["metadata"])
        self.assertEqual(meta["market_mode"], "HISTORICAL_REPLAY")
        self.assertEqual(meta["dataset_id"], "HIST_20261110_COT")
        self.assertIn("price_nature", meta)
        self.assertIn("simulated_market_datetime_cot", meta)
        print(f"[OK] Metadatos forenses guardados: Naturaleza '{meta['price_nature']}', Hora COT '{meta['simulated_market_datetime_cot']}'.")

        # 7. Advance and Execute SELL
        time.sleep(0.5)
        sell_res = client.post("/api/participant/trade", json={"side": "SELL", "asset": "USDT", "amount": 1000, "quote_type": "CRYPTO"}, headers=p_headers)
        self.assertEqual(sell_res.status_code, 200)
        print("[OK] Venta posterior ejecutada con cotización sincronizada.")

        # 8. Forensic Audit & Mathematical Reconciliation
        inv_res = client.get(f"/api/admin/rooms/{room_code}/investigate/TRADER_REPLAY", headers=headers)
        self.assertEqual(inv_res.status_code, 200)
        inv_data = inv_res.json()
        self.assertEqual(inv_data["reconciliation"]["status"], "CONCILIACIÓN_PERFECTA")
        self.assertEqual(inv_data["reconciliation"]["bank"]["discrepancy"], 0.0)
        self.assertEqual(inv_data["reconciliation"]["wallet_cop"]["discrepancy"], 0.0)
        self.assertEqual(inv_data["reconciliation"]["crypto"]["USDT"]["discrepancy"], 0.0)
        print("[OK] Conciliación contable pericial verificada al 100% (Discrepancia contable: COP 0.00).")

        print("=" * 65)
        print(" TODOS LOS REQUISITOS DEL MOTOR Y CORRECCIONES VALIDADOS CON EXITO")
        print("=" * 65)

if __name__ == "__main__":
    unittest.main()
