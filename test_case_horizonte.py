import os
import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal

# Ensure utf-8 terminal output if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import uuid
from database import init_db, get_db_connection, round_amount
from forensics import analyze_participant
from replay_engine import MarketReplayEngine

def get_now_iso():
    return datetime.now(timezone.utc).isoformat()

class TestCaseHorizonte(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db = os.environ.get("CRYPTOLAB_DB")
        cls.test_db = f"temp_test_horiz_{uuid.uuid4().hex[:6]}.db"
        os.environ["CRYPTOLAB_DB"] = cls.test_db
        init_db(cls.test_db)
        cls.conn = get_db_connection(cls.test_db)
        cls.cur = cls.conn.cursor()

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

    def test_complete_simulation_pipeline(self):
        print("\n" + "=" * 65)
        print(" EJECUTANDO PRUEBA OFICIAL DEL CASO COMERCIALIZADORA HORIZONTE")
        print("=" * 65)

        # 1. Crear Sala de prueba
        room_code = "SALA_HORIZONTE"
        room_name = "Caso Demostrativo Comercializadora Horizonte S.A.S."
        init_balance = 50000000.0 # 50 Millones COP
        now_iso = get_now_iso()

        self.cur.execute("""
            INSERT INTO rooms (code, name, status, initial_bank_balance_cop, created_at)
            VALUES (?, ?, 'OPEN', ?, ?)
        """, (room_code, room_name, init_balance, now_iso))
        self.conn.commit()
        print(f"[OK] Paso 1: Sala '{room_code}' creada con saldo inicial de COP {init_balance:,.2f}")

        # 2. Registrar Participantes: HORIZONTE, USUARIO_B, USUARIO_C
        participants = ["HORIZONTE", "USUARIO_B", "USUARIO_C"]
        part_data = {}

        for alias in participants:
            p_id = f"usr_{alias.lower()}"
            token = f"tok_{alias.lower()}"
            self.cur.execute("""
                INSERT INTO participants (
                    id, room_code, alias, alias_normalized, session_token,
                    bank_balance_cop, wallet_cop, wallet_btc, wallet_eth, wallet_usdt, wallet_sol,
                    created_at, last_active_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, 0.0, 0.0, 0.0, ?, ?)
            """, (p_id, room_code, alias, alias.upper(), token, init_balance, now_iso, now_iso))

            self.cur.execute("""
                INSERT INTO transactions (
                    id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                    asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                    tx_hash, status, metadata, created_at
                ) VALUES (?, ?, 'DEPOSIT_INITIAL_ENDOWMENT', 'SISTEMA_CENTRAL', ?, 0, 'COP', ?, 0.0, 1.0, ?, ?, ?, 'CONFIRMED', 'Dotacion inicial', ?)
            """, (f"TX-INIT-{alias}", room_code, alias, init_balance, init_balance, init_balance, f"0xinit{alias.lower()}", now_iso))

            part_data[alias] = p_id

        self.conn.commit()
        print("[OK] Paso 2: Participantes registrados (HORIZONTE, USUARIO_B, USUARIO_C) con 50M COP cada uno.")

        # 3. HORIZONTE traslada 45,000,000 COP de Banco a Billetera
        transfer_bank_amt = 45000000.0
        self.cur.execute("""
            UPDATE participants 
            SET bank_balance_cop = bank_balance_cop - ?, wallet_cop = wallet_cop + ? 
            WHERE alias = 'HORIZONTE'
        """, (transfer_bank_amt, transfer_bank_amt))

        self.cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES ('TX-BNK-01', ?, 'DEPOSIT_BANK_TO_WALLET', 'HORIZONTE', 'HORIZONTE', 0, 'COP', ?, 0.0, 1.0, ?, ?, '0xbnk01hash', 'CONFIRMED', 'Traslado a billetera', ?)
        """, (room_code, transfer_bank_amt, transfer_bank_amt, transfer_bank_amt, now_iso))
        self.conn.commit()
        print(f"[OK] Paso 3: HORIZONTE traslado {transfer_bank_amt:,.2f} COP de Banco a Billetera.")

        # 4. HORIZONTE compra 10,000 USDT utilizando el Motor Market Replay (TRM oficial BanRep $3.269,88)
        engine = MarketReplayEngine.get_instance()
        engine.reset() # Sincroniza al inicio del 10-Nov (00:00:00 COT)
        quote = engine.get_price_for_trade("USDT")
        usdt_price = quote["price_cop"]
        usdt_amount = 10000.0
        gross_cop = round(usdt_amount * usdt_price, 2)
        fee_cop = round(gross_cop * 0.002, 2) # 0.2% de comisión de plataforma
        total_cop_debited = gross_cop + fee_cop

        meta_trade = json.dumps({
            "test_environment": "PRUEBA_AISLADA_CONTROLADA",
            "execution_mechanism": "MARKET_REPLAY_ENGINE",
            "price_nature": quote["price_type"],
            "unit_price_cop": usdt_price,
            "trm_applied": quote["trm_applied"],
            "simulated_market_datetime_cot": quote["simulated_datetime_cot"]
        }, ensure_ascii=False)

        self.cur.execute("""
            UPDATE participants 
            SET wallet_cop = wallet_cop - ?, wallet_usdt = wallet_usdt + ? 
            WHERE alias = 'HORIZONTE'
        """, (total_cop_debited, usdt_amount))

        self.cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES ('TX-BUY-01', ?, 'BUY_CRYPTO', 'HORIZONTE', 'MERCADO_SIMULADO', 0, 'USDT', ?, ?, ?, ?, ?, '0xbuy01hash', 'CONFIRMED', ?, ?)
        """, (room_code, usdt_amount, fee_cop, usdt_price, gross_cop, gross_cop, meta_trade, now_iso))
        self.conn.commit()
        print(f"[OK] Paso 4: HORIZONTE compró {usdt_amount} USDT @ COP {usdt_price:,.2f} vía Market Replay (Total: COP {gross_cop:,.2f} + Comisión 0.2%: COP {fee_cop:,.2f}).")

        # 5. HORIZONTE transfiere 10,000 USDT a USUARIO_B (P2P Interno)
        self.cur.execute("""
            UPDATE participants SET wallet_usdt = wallet_usdt - ? WHERE alias = 'HORIZONTE'
        """, (usdt_amount,))
        self.cur.execute("""
            UPDATE participants SET wallet_usdt = wallet_usdt + ? WHERE alias = 'USUARIO_B'
        """, (usdt_amount,))

        self.cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES ('TX-INT-01', ?, 'TRANSFER_INTERNAL', 'HORIZONTE', 'USUARIO_B', 0, 'USDT', ?, 0.0, NULL, NULL, NULL, '0xint01hash', 'CONFIRMED', 'Transferencia P2P', ?)
        """, (room_code, usdt_amount, now_iso))
        self.conn.commit()
        print(f"[OK] Paso 5: Transferencia interna 1: HORIZONTE -> USUARIO_B ({usdt_amount} USDT).")

        # 6. USUARIO_B transfiere 10,000 USDT a USUARIO_C (P2P Interno)
        self.cur.execute("""
            UPDATE participants SET wallet_usdt = wallet_usdt - ? WHERE alias = 'USUARIO_B'
        """, (usdt_amount,))
        self.cur.execute("""
            UPDATE participants SET wallet_usdt = wallet_usdt + ? WHERE alias = 'USUARIO_C'
        """, (usdt_amount,))

        self.cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES ('TX-INT-02', ?, 'TRANSFER_INTERNAL', 'USUARIO_B', 'USUARIO_C', 0, 'USDT', ?, 0.0, NULL, NULL, NULL, '0xint02hash', 'CONFIRMED', 'Transferencia P2P', ?)
        """, (room_code, usdt_amount, now_iso))
        self.conn.commit()
        print(f"[OK] Paso 6: Transferencia interna 2: USUARIO_B -> USUARIO_C ({usdt_amount} USDT).")

        # 7. USUARIO_C transfiere 10,000 USDT a direccion externa simulada
        ext_address = "0x98A7F4c1D83e1E7938A99bc7b26d8591B9A1"
        self.cur.execute("""
            UPDATE participants SET wallet_usdt = wallet_usdt - ? WHERE alias = 'USUARIO_C'
        """, (usdt_amount,))

        self.cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES ('TX-EXT-01', ?, 'TRANSFER_EXTERNAL', 'USUARIO_C', ?, 1, 'USDT', ?, 0.0, NULL, NULL, NULL, '0xext01hash', 'CONFIRMED', 'Salida externa', ?)
        """, (room_code, ext_address, usdt_amount, now_iso))
        self.conn.commit()
        print(f"[OK] Paso 7: Transferencia externa: USUARIO_C -> {ext_address} ({usdt_amount} USDT). Fin de trazabilidad.")

        # 8. EJECUTAR AUDITORIA FORENSE SOBRE HORIZONTE
        print("\n" + "=" * 65)
        print(" AUDITORIA FORENSE AUTOMATIZADA: ANALIZANDO A 'HORIZONTE'")
        print("=" * 65)

        report = analyze_participant(room_code, "HORIZONTE", db_conn=self.conn)

        # Verificaciones criticas
        # A. Conciliacion Contable
        rec = report["reconciliation"]
        self.assertEqual(rec["status"], "CONCILIACIÓN_PERFECTA", "La conciliacion debe ser perfecta.")
        self.assertEqual(rec["bank"]["discrepancy"], 0.0, "La discrepancia bancaria debe ser 0.")
        self.assertEqual(rec["wallet_cop"]["discrepancy"], 0.0, "La discrepancia en billetera COP debe ser 0.")
        self.assertEqual(rec["crypto"]["USDT"]["discrepancy"], 0.0, "La discrepancia en USDT debe ser 0.")
        print("[TEST PASSED] Conciliacion matematica perfecta (Discrepancia contable = 0.00).")

        # B. Saldos finales de HORIZONTE
        p_bal = report["participant"]["balances"]
        self.assertEqual(p_bal["bank_cop"], 5000000.0)
        expected_wallet_cop = round(transfer_bank_amt - total_cop_debited, 2)
        self.assertEqual(p_bal["wallet_cop"], expected_wallet_cop)
        self.assertEqual(p_bal["wallet_usdt"], 0.0)
        print(f"[TEST PASSED] Saldos de HORIZONTE verificados: Banco COP {p_bal['bank_cop']:,.2f}, Billetera COP {p_bal['wallet_cop']:,.2f}, USDT {p_bal['wallet_usdt']}.")

        # C. Reconstruccion del Grafo y Cadenas
        graph = report["graph"]
        chains = graph["chains"]
        self.assertGreaterEqual(len(chains), 1, "Debe reconstruir al menos 1 cadena de transferencias.")
        
        ext_chain = next((c for c in chains if c["reaches_external"]), None)
        self.assertIsNotNone(ext_chain, "Debe identificar la cadena que alcanza el destino externo simulado.")
        
        expected_path = ["HORIZONTE", "USUARIO_B", "USUARIO_C", ext_address]
        self.assertEqual(ext_chain["path"], expected_path, f"La ruta debe ser {expected_path}, obtenida: {ext_chain['path']}")
        print(f"[TEST PASSED] Cadena multietapa reconstruida con exito: {' -> '.join(ext_chain['path'])}.")

        # D. Alertas de Riesgo Detectadas
        alerts = report["alerts"]
        alert_codes = [a["code"] for a in alerts]
        self.assertIn("ALT_FAST_CONV_TRANSFER", alert_codes, "Debe detectar compra rapida seguida de transferencia.")
        print(f"[TEST PASSED] Alertas detectadas correctamente: {', '.join(alert_codes)}.")

        # E. Hallazgos Objetivos
        findings = report["findings"]
        self.assertGreaterEqual(len(findings), 4, "Debe generar al menos 4 hallazgos objetivos.")
        print(f"[TEST PASSED] {len(findings)} Hallazgos facticos generados automaticamente.")

        # F. Verificar tambien la auditoria de USUARIO_B y USUARIO_C
        report_b = analyze_participant(room_code, "USUARIO_B", db_conn=self.conn)
        self.assertEqual(report_b["reconciliation"]["status"], "CONCILIACIÓN_PERFECTA")
        print("[TEST PASSED] Auditoria de USUARIO_B conciliada al 100%.")

        report_c = analyze_participant(room_code, "USUARIO_C", db_conn=self.conn)
        self.assertEqual(report_c["reconciliation"]["status"], "CONCILIACIÓN_PERFECTA")
        print("[TEST PASSED] Auditoria de USUARIO_C conciliada al 100%.")

        print("=" * 65)
        print(" TODOS LOS REQUISITOS DEL CASO HORIZONTE VALIDADOS SATISFACTORIAMENTE")
        print("=" * 65)

if __name__ == "__main__":
    unittest.main()
