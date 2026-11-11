import os
import sys
import unittest
import uuid

# Ensure utf-8 terminal output if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from starlette.testclient import TestClient
from database import init_db, get_admin_credentials
from server import app

client = None

class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global client
        cls.orig_db = os.environ.get("CRYPTOLAB_DB")
        cls.test_db = f"temp_test_api_{uuid.uuid4().hex[:6]}.db"
        os.environ["CRYPTOLAB_DB"] = cls.test_db
        init_db(cls.test_db)
        client = TestClient(app)

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

    def test_static_routes(self):
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("CRYPTO LAB", resp.text)

        resp_admin = client.get("/admin")
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn("CENTRO DE CONTROL", resp_admin.text)

    def test_network_info(self):
        resp = client.get("/api/network-info")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("lan_ip", data)
        self.assertIn("port", data)
        self.assertIn("participant_url", data)

    def test_market_prices(self):
        resp = client.get("/api/market/prices")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prices", data)
        self.assertIn("BTC", data["prices"])
        self.assertIn("USDT", data["prices"])
        # Check price nature exists
        self.assertIn("nature", data["prices"]["BTC"])
        self.assertIn(data["prices"]["BTC"]["nature"], ("OBSERVADO_REAL", "CALCULADO_INTERPOLADO"))

    def test_admin_flow(self):
        # Get secure credentials from .env
        admin_u, admin_p = get_admin_credentials()
        
        # Login using secure credentials
        resp = client.post("/api/admin/login", json={"username": admin_u, "password": admin_p})
        self.assertEqual(resp.status_code, 200, f"Login failed for {admin_u}")
        token = resp.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Create room
        room_code = f"DEMO{uuid.uuid4().hex[:4].upper()}"
        r_create = client.post("/api/admin/rooms", json={"code": room_code, "name": "Sala Demo", "initial_bank_balance_cop": 50000000}, headers=headers)
        self.assertEqual(r_create.status_code, 200)

        # Check QR code
        qr_resp = client.get(f"/api/rooms/{room_code}/qr?format=svg")
        self.assertEqual(qr_resp.status_code, 200)
        self.assertIn("<svg", qr_resp.text)

        # Join participant
        p_resp = client.post("/api/rooms/join", json={"room_code": room_code, "alias": "TEST_USER"})
        self.assertEqual(p_resp.status_code, 200)
        p_token = p_resp.json()["token"]
        p_headers = {"Authorization": f"Bearer {p_token}"}

        # Check me
        me_resp = client.get("/api/participant/me", headers=p_headers)
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["participant"]["bank_balance_cop"], 50000000.0)

        # Bank transfer (Deposit to wallet)
        bnk_resp = client.post("/api/participant/bank-transfer", json={"action": "DEPOSIT", "amount": 10000000}, headers=p_headers)
        self.assertEqual(bnk_resp.status_code, 200)

        # Trade Buy USDT
        trade_resp = client.post("/api/participant/trade", json={"side": "BUY", "asset": "USDT", "amount": 1000, "quote_type": "CRYPTO"}, headers=p_headers)
        self.assertEqual(trade_resp.status_code, 200)

        # Investigate via admin
        inv_resp = client.get(f"/api/admin/rooms/{room_code}/investigate/TEST_USER", headers=headers)
        self.assertEqual(inv_resp.status_code, 200)
        inv_data = inv_resp.json()
        self.assertEqual(inv_data["reconciliation"]["status"], "CONCILIACIÓN_PERFECTA")
        print("[OK] Todos los endpoints de la API respondieron exitosamente usando base de datos aislada temporal.")

    def test_concurrent_multi_device_access(self):
        """Simulate concurrent requests from two distinct devices/participants on the same network."""
        import concurrent.futures
        admin_u, admin_p = get_admin_credentials()
        login_res = client.post("/api/admin/login", json={"username": admin_u, "password": admin_p})
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        room_code = f"CONC{uuid.uuid4().hex[:4].upper()}"
        client.post("/api/admin/rooms", json={"code": room_code, "name": "Sala Concurrente", "initial_bank_balance_cop": 50000000}, headers=headers)

        # Device 1 joins
        dev1_res = client.post("/api/rooms/join", json={"room_code": room_code, "alias": "DISPOSITIVO_CELULAR_1"})
        self.assertEqual(dev1_res.status_code, 200)
        token1 = dev1_res.json()["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Device 2 joins
        dev2_res = client.post("/api/rooms/join", json={"room_code": room_code, "alias": "DISPOSITIVO_CELULAR_2"})
        self.assertEqual(dev2_res.status_code, 200)
        token2 = dev2_res.json()["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Step A: Both move funds from bank to wallet concurrently
        def move_funds(h, amt):
            return client.post("/api/participant/bank-transfer", json={"action": "DEPOSIT", "amount": amt}, headers=h)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(move_funds, headers1, 20000000)
            f2 = executor.submit(move_funds, headers2, 30000000)
            res1 = f1.result()
            res2 = f2.result()

        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)

        # Step B: Both trade concurrently (Buy USDT and Buy BTC)
        def do_trade(h, asset, amt):
            return client.post("/api/participant/trade", json={"side": "BUY", "asset": asset, "amount": amt, "quote_type": "CRYPTO"}, headers=h)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            t1 = executor.submit(do_trade, headers1, "USDT", 2000)
            t2 = executor.submit(do_trade, headers2, "BTC", 0.05)
            trade_res1 = t1.result()
            trade_res2 = t2.result()

        self.assertEqual(trade_res1.status_code, 200)
        self.assertEqual(trade_res2.status_code, 200)

        # Step C: Device 1 transfers USDT to Device 2
        p2p_res = client.post("/api/participant/transfer", json={
            "transfer_type": "INTERNAL",
            "destination_alias": "DISPOSITIVO_CELULAR_2",
            "asset": "USDT",
            "amount": 1000,
            "notes": "P2P Concurrente Celular 1 a 2"
        }, headers=headers1)
        self.assertEqual(p2p_res.status_code, 200)

        # Step D: Verify forensic reconciliation for both concurrent devices
        inv1 = client.get(f"/api/admin/rooms/{room_code}/investigate/DISPOSITIVO_CELULAR_1", headers=headers).json()
        inv2 = client.get(f"/api/admin/rooms/{room_code}/investigate/DISPOSITIVO_CELULAR_2", headers=headers).json()

        self.assertEqual(inv1["reconciliation"]["status"], "CONCILIACIÓN_PERFECTA")
        self.assertEqual(inv1["reconciliation"]["bank"]["discrepancy"], 0.0)
        self.assertEqual(inv1["reconciliation"]["wallet_cop"]["discrepancy"], 0.0)
        self.assertEqual(inv1["reconciliation"]["crypto"]["USDT"]["discrepancy"], 0.0)

        self.assertEqual(inv2["reconciliation"]["status"], "CONCILIACIÓN_PERFECTA")
        self.assertEqual(inv2["reconciliation"]["bank"]["discrepancy"], 0.0)
        self.assertEqual(inv2["reconciliation"]["wallet_cop"]["discrepancy"], 0.0)
        self.assertEqual(inv2["reconciliation"]["crypto"]["USDT"]["discrepancy"], 0.0)
        self.assertEqual(inv2["reconciliation"]["crypto"]["BTC"]["discrepancy"], 0.0)

        # Check asset conservation: Device 1 has 1000 USDT, Device 2 has 1000 USDT (Total = 2000 USDT bought)
        self.assertEqual(inv1["participant"]["balances"]["wallet_usdt"], 1000.0)
        self.assertEqual(inv2["participant"]["balances"]["wallet_usdt"], 1000.0)
        print("[OK] Acceso concurrente desde 2 dispositivos validado exitosamente sin duplicación de activos ni bloqueos.")

if __name__ == "__main__":
    unittest.main()
