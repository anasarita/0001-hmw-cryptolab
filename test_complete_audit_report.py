import os
import sys
import unittest
import uuid
from decimal import Decimal

from database import init_db, get_db_connection, generate_tx_hash
from forensics import analyze_participant

class TestAuditReportAndTransactionHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db = os.environ.get("CRYPTOLAB_DB")
        cls.test_db = f"temp_test_audit_{uuid.uuid4().hex[:6]}.db"
        os.environ["CRYPTOLAB_DB"] = cls.test_db
        init_db(cls.test_db)
        cls.conn = get_db_connection(cls.test_db)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass
        if cls.orig_db:
            os.environ["CRYPTOLAB_DB"] = cls.orig_db
        else:
            os.environ.pop("CRYPTOLAB_DB", None)

    def test_complete_operations_and_executive_report(self):
        cur = self.conn.cursor()
        room_code = "ROOM_EXEC_01"
        now_iso = "2026-11-10T10:00:00-05:00"

        # Create Room
        cur.execute("""
            INSERT INTO rooms (code, name, initial_bank_balance_cop, status, created_at)
            VALUES (?, ?, 50000000.0, 'OPEN', ?)
        """, (room_code, "Sesión Auditoría Ejecutiva", now_iso))

        # Register Participants
        alias_a = "EMPRESA_ALPHA"
        alias_b = "INTERMEDIARIO_BETA"
        cur.execute("""
            INSERT INTO participants (
                id, room_code, alias, alias_normalized, session_token,
                bank_balance_cop, wallet_cop, wallet_btc, wallet_eth, wallet_usdt, wallet_sol,
                created_at, last_active_at
            ) VALUES 
            ('p1', ?, ?, ?, 'tok1', 5000000.0, 12270571.80, 0.0, 0.0, 0.0, 0.0, ?, ?),
            ('p2', ?, ?, ?, 'tok2', 50000000.0, 0.0, 0.0, 0.0, 0.0, 0.0, ?, ?)
        """, (room_code, alias_a, alias_a.upper(), now_iso, now_iso,
              room_code, alias_b, alias_b.upper(), now_iso, now_iso))

        # 1. Saldo inicial asignado
        tx1_id = "TX-INIT-001"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'DEPOSIT_INITIAL_ENDOWMENT', 'SISTEMA_CENTRAL', ?, 0, 'COP', 50000000.0, 0.0, 1.0, 50000000.0, 50000000.0, ?, 'CONFIRMED', 'Dotación inicial', ?)
        """, (tx1_id, room_code, alias_a, generate_tx_hash(tx1_id, 'SISTEMA_CENTRAL', alias_a, 'COP', 50000000.0, now_iso), now_iso))

        # 2. Traslado banco -> billetera
        tx2_id = "TX-BNK-001"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'DEPOSIT_BANK_TO_WALLET', ?, ?, 0, 'COP', 45000000.0, 0.0, 1.0, 45000000.0, 45000000.0, ?, 'CONFIRMED', 'Traslado banco a billetera', ?)
        """, (tx2_id, room_code, alias_a, alias_a, generate_tx_hash(tx2_id, alias_a, alias_a, 'COP', 45000000.0, now_iso), now_iso))

        # 3. Traslado billetera -> banco
        tx3_id = "TX-BNK-002"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'WITHDRAW_WALLET_TO_BANK', ?, ?, 0, 'COP', 5000000.0, 0.0, 1.0, 5000000.0, 5000000.0, ?, 'CONFIRMED', 'Traslado billetera a banco', ?)
        """, (tx3_id, room_code, alias_a, alias_a, generate_tx_hash(tx3_id, alias_a, alias_a, 'COP', 5000000.0, now_iso), now_iso))

        # 4. Compra de cripto con comisión
        tx4_id = "TX-BUY-001"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'BUY_CRYPTO', ?, 'MERCADO_SIMULADO', 0, 'USDT', 10000.0, 65328.20, 3266.41, 32664100.0, 32664100.0, ?, 'CONFIRMED', 'Compra en mercado', ?)
        """, (tx4_id, room_code, alias_a, generate_tx_hash(tx4_id, alias_a, 'MERCADO_SIMULADO', 'USDT', 10000.0, now_iso), now_iso))

        # 5. Venta de cripto con comisión
        tx5_id = "TX-SEL-001"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'SELL_CRYPTO', ?, 'MERCADO_SIMULADO', 0, 'BTC', 0.01, 4883.69, 244184510.13, 2441845.10, 2436961.41, ?, 'CONFIRMED', 'Venta en mercado', ?)
        """, (tx5_id, room_code, alias_a, generate_tx_hash(tx5_id, alias_a, 'MERCADO_SIMULADO', 'BTC', 0.01, now_iso), now_iso))

        # 6. Transferencia interna entre participantes
        tx6_id = "TX-INT-001"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'TRANSFER_INTERNAL', ?, ?, 0, 'USDT', 5000.0, 0.0, 3266.41, 16332050.0, 16332050.0, ?, 'CONFIRMED', 'Transferencia interna P2P', ?)
        """, (tx6_id, room_code, alias_a, alias_b, generate_tx_hash(tx6_id, alias_a, alias_b, 'USDT', 5000.0, now_iso), now_iso))

        # 7. Transferencia a destino externo simulado
        tx7_id = "TX-EXT-001"
        ext_addr = "0x71C934E89B9aF5c12891b29A1A"
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'TRANSFER_EXTERNAL', ?, ?, 1, 'USDT', 5000.0, 0.0, 3266.41, 16332050.0, 16332050.0, ?, 'CONFIRMED', 'Salida externa de fondos', ?)
        """, (tx7_id, room_code, alias_a, ext_addr, generate_tx_hash(tx7_id, alias_a, ext_addr, 'USDT', 5000.0, now_iso), now_iso))

        self.conn.commit()

        # Run Forensic Investigation
        report = analyze_participant(room_code, alias_a, db_conn=self.conn)

        # Validate Executive Summary (5.2)
        exec_sum = report.get("executive_summary")
        self.assertIsNotNone(exec_sum, "Debe generar resumen ejecutivo.")
        self.assertEqual(exec_sum["total_operations_analyzed"], 7)
        self.assertIn("USDT", exec_sum["assets_involved"])
        self.assertIn(exec_sum["risk_level"], ("BAJO", "MEDIO", "ALTO"))

        # Validate Financial Summary (5.3)
        fin = report["financial_summary"]
        self.assertEqual(fin["initial_balance_cop"], 50000000.0)
        self.assertEqual(fin["total_purchases_cop"], 32664100.0)
        self.assertEqual(fin["total_internal_transfers_sent"], 1)
        self.assertEqual(fin["total_external_transfers"], 1)

        # Validate Risk Alerts (5.4)
        alerts = report["alerts"]
        self.assertTrue(len(alerts) >= 1, "Debe detectar al menos una alerta técnica.")
        for a in alerts:
            self.assertIn("impact", a, "Cada alerta debe contener lectura de impacto técnico.")
            self.assertIn(a["severity"], ("BAJO", "MEDIO", "ALTO"))

        # Validate Traceability (5.5)
        chains = report["graph"]["chains"]
        self.assertTrue(len(chains) >= 1, "Debe identificar cadenas de trazabilidad.")

        # Validate Findings (5.6)
        findings = report["findings"]
        self.assertTrue(3 <= len(findings) <= 7, "Debe tener entre 3 y 7 hallazgos fácticos.")

        # Validate Conclusion (5.7)
        conclusion = report.get("executive_conclusion")
        self.assertIsNotNone(conclusion, "Debe incluir conclusión ejecutiva breve.")
        self.assertIn("trazabilidad", conclusion.lower())

        print("[TEST PASSED] Auditoría forense ejecutiva de 7 secciones validada con éxito.")

if __name__ == "__main__":
    unittest.main()
