import os
import io
import json
import socket
import uuid
import hashlib
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, Depends, Query, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import qrcode
from qrcode.image.svg import SvgImage

from database import init_db, get_db_connection, generate_tx_hash, round_amount, get_admin_credentials, hash_admin_password
from prices import get_market_prices
from forensics import analyze_participant

# Initialize database schema
init_db()

app = FastAPI(title="Crypto Lab - Simulador & Auditoría Forense", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_now_iso():
    return datetime.now(timezone.utc).isoformat()

# Helper to find LAN IP
def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# --- PYDANTIC SCHEMAS ---

class AdminLoginReq(BaseModel):
    username: str
    password: str

class CreateRoomReq(BaseModel):
    code: str
    name: str
    initial_bank_balance_cop: float = 50000000.0

class JoinRoomReq(BaseModel):
    room_code: str
    alias: str

class BankTransferReq(BaseModel):
    action: str # "DEPOSIT" (Bank -> Wallet), "WITHDRAW" (Wallet -> Bank)
    amount: float

class TradeReq(BaseModel):
    side: str # "BUY", "SELL"
    asset: str # "BTC", "ETH", "USDT", "SOL"
    amount: float # amount in crypto or cop depending on quote_type
    quote_type: str = "CRYPTO" # "CRYPTO" or "COP"

class TransferReq(BaseModel):
    transfer_type: str # "INTERNAL", "EXTERNAL"
    asset: str # "COP", "BTC", "ETH", "USDT", "SOL"
    amount: float
    destination_alias: Optional[str] = None
    external_address: Optional[str] = None
    notes: Optional[str] = None

# --- AUTH HELPERS ---

def get_current_participant(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sesión no suministrada o inválida.")
    token = authorization.split(" ")[1].strip()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM participants WHERE session_token = ?", (token,))
    part = cur.fetchone()
    if not part:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión expirada o no encontrada.")
    
    # Update last active
    cur.execute("UPDATE participants SET last_active_at = ? WHERE id = ?", (get_now_iso(), part["id"]))
    conn.commit()
    conn.close()
    return dict(part)

def get_current_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Autenticación de administrador requerida.")
    token = authorization.split(" ")[1].strip()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins WHERE session_token = ?", (token,))
    admin = cur.fetchone()
    conn.close()
    if not admin:
        raise HTTPException(status_code=401, detail="Sesión de administrador inválida o expirada.")
    return dict(admin)

# --- SYSTEM & NETWORK ENDPOINTS ---

@app.get("/api/network-info")
def get_network_info():
    lan_ip = get_lan_ip()
    port = int(os.environ.get("PORT", 8000))
    return {
        "lan_ip": lan_ip,
        "port": port,
        "participant_url": f"http://{lan_ip}:{port}",
        "admin_url": f"http://{lan_ip}:{port}/admin",
        "local_participant_url": f"http://localhost:{port}",
        "local_admin_url": f"http://localhost:{port}/admin"
    }

@app.get("/api/rooms/{code}/qr")
def get_room_qr(code: str, format: str = "svg"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT code, name FROM rooms WHERE code = ?", (code.strip().upper(),))
    room = cur.fetchone()
    conn.close()
    if not room:
        raise HTTPException(status_code=404, detail="Sala no encontrada.")

    lan_ip = get_lan_ip()
    port = int(os.environ.get("PORT", 8000))
    join_url = f"http://{lan_ip}:{port}/?room={room['code']}"

    if format == "svg":
        img = qrcode.make(join_url, image_factory=SvgImage)
        buf = io.BytesIO()
        img.save(buf)
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/svg+xml")
    else:
        img = qrcode.make(join_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

from replay_engine import MarketReplayEngine

# --- MARKET REPLAY & PRICES ---

@app.get("/api/market/replay-status")
def get_replay_status():
    engine = MarketReplayEngine.get_instance()
    return engine.get_state()

@app.get("/api/market/prices")
async def get_prices():
    prices = await get_market_prices()
    engine = MarketReplayEngine.get_instance()
    state = engine.get_state()
    return {
        "timestamp": get_now_iso(),
        "prices": prices,
        "replay_state": state
    }

@app.post("/api/admin/replay/play")
def admin_replay_play(admin: dict = Depends(get_current_admin)):
    engine = MarketReplayEngine.get_instance()
    engine.play()
    return {"message": "Market Replay iniciado/reanudado.", "state": engine.get_state()}

@app.post("/api/admin/replay/pause")
def admin_replay_pause(admin: dict = Depends(get_current_admin)):
    engine = MarketReplayEngine.get_instance()
    engine.pause()
    return {"message": "Market Replay pausado.", "state": engine.get_state()}

@app.post("/api/admin/replay/reset")
def admin_replay_reset(admin: dict = Depends(get_current_admin)):
    engine = MarketReplayEngine.get_instance()
    engine.reset()
    return {"message": "Market Replay reiniciado al inicio de la jornada.", "state": engine.get_state()}

@app.post("/api/admin/replay/speed")
def admin_replay_speed(speed: float = Query(..., ge=0.1, le=500.0), admin: dict = Depends(get_current_admin)):
    engine = MarketReplayEngine.get_instance()
    engine.set_speed(speed)
    return {"message": f"Velocidad ajustada a {speed}x.", "state": engine.get_state()}

# --- ADMIN ENDPOINTS ---

@app.post("/api/admin/login")
def admin_login(req: AdminLoginReq):
    pass_hash = hash_admin_password(req.password)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins WHERE username = ? AND password_hash = ?", (req.username.strip(), pass_hash))
    admin = cur.fetchone()
    if not admin:
        conn.close()
        raise HTTPException(status_code=401, detail="Usuario o contraseña de administrador incorrectos.")
    
    token = f"adm_{uuid.uuid4().hex}"
    cur.execute("UPDATE admins SET session_token = ? WHERE username = ?", (token, req.username.strip()))
    
    # Audit log
    cur.execute(
        "INSERT INTO admin_audit_log (action, details, created_at) VALUES (?, ?, ?)",
        ("ADMIN_LOGIN", f"Admin '{req.username}' inició sesión.", get_now_iso())
    )
    conn.commit()
    conn.close()
    
    return {"token": token, "username": req.username}

@app.get("/api/admin/me")
def admin_me(admin: dict = Depends(get_current_admin)):
    return {"username": admin["username"]}

@app.get("/api/admin/rooms")
def list_rooms(admin: dict = Depends(get_current_admin)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, 
               (SELECT COUNT(*) FROM participants p WHERE p.room_code = r.code) as participant_count,
               (SELECT COUNT(*) FROM transactions t WHERE t.room_code = r.code) as tx_count
        FROM rooms r 
        ORDER BY r.created_at DESC
    """)
    rooms = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"rooms": rooms}

@app.post("/api/admin/rooms")
def create_room(req: CreateRoomReq, admin: dict = Depends(get_current_admin)):
    code = req.code.strip().upper()
    if not code or len(code) < 3:
        raise HTTPException(status_code=400, detail="El código de sala debe tener al menos 3 caracteres alfanuméricos.")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT code FROM rooms WHERE code = ?", (code,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"La sala con código '{code}' ya existe.")

    now_iso = get_now_iso()
    cur.execute(
        "INSERT INTO rooms (code, name, status, initial_bank_balance_cop, created_at) VALUES (?, ?, 'OPEN', ?, ?)",
        (code, req.name.strip(), float(req.initial_bank_balance_cop), now_iso)
    )
    
    cur.execute(
        "INSERT INTO admin_audit_log (action, details, created_at) VALUES (?, ?, ?)",
        ("CREATE_ROOM", f"Sala creada: {code} ({req.name}) con saldo inicial {req.initial_bank_balance_cop:,.2f} COP", now_iso)
    )
    conn.commit()
    conn.close()
    return {"message": "Sala creada con éxito.", "code": code}

@app.patch("/api/admin/rooms/{code}/status")
def toggle_room_status(code: str, status: str = Query(..., pattern="^(OPEN|CLOSED)$"), admin: dict = Depends(get_current_admin)):
    code = code.strip().upper()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms WHERE code = ?", (code,))
    room = cur.fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail="Sala no encontrada.")

    now_iso = get_now_iso()
    cur.execute(
        "UPDATE rooms SET status = ?, closed_at = ? WHERE code = ?",
        (status, now_iso if status == "CLOSED" else None, code)
    )
    cur.execute(
        "INSERT INTO admin_audit_log (action, details, created_at) VALUES (?, ?, ?)",
        ("UPDATE_ROOM_STATUS", f"Sala {code} cambió estado a {status}.", now_iso)
    )
    conn.commit()
    conn.close()
    return {"message": f"Estado de la sala actualizado a {status}."}

@app.get("/api/admin/rooms/{code}/stats")
def get_room_stats(code: str, admin: dict = Depends(get_current_admin)):
    code = code.strip().upper()
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM rooms WHERE code = ?", (code,))
    room = cur.fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail="Sala no encontrada.")

    # Total volume, fees, transactions
    cur.execute("""
        SELECT 
            COUNT(*) as total_txs,
            SUM(CASE WHEN tx_type IN ('BUY_CRYPTO', 'SELL_CRYPTO') THEN gross_amount_cop ELSE 0 END) as total_volume_cop,
            SUM(fee_cop) as total_fees_cop,
            SUM(CASE WHEN tx_type = 'TRANSFER_INTERNAL' THEN 1 ELSE 0 END) as internal_transfers,
            SUM(CASE WHEN tx_type = 'TRANSFER_EXTERNAL' THEN 1 ELSE 0 END) as external_transfers
        FROM transactions WHERE room_code = ?
    """, (code,))
    stats = dict(cur.fetchone())

    # Participants with total balances
    cur.execute("""
        SELECT id, alias, bank_balance_cop, wallet_cop, wallet_btc, wallet_eth, wallet_usdt, wallet_sol, created_at, last_active_at,
               (SELECT COUNT(*) FROM transactions WHERE room_code = ? AND (sender_alias = p.alias OR receiver_alias = p.alias)) as tx_count
        FROM participants p 
        WHERE room_code = ? 
        ORDER BY created_at ASC
    """, (code, code))
    participants = [dict(r) for r in cur.fetchall()]

    # Last 15 transactions
    cur.execute("""
        SELECT * FROM transactions WHERE room_code = ? ORDER BY created_at DESC LIMIT 20
    """, (code,))
    recent_txs = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "room": dict(room),
        "stats": stats,
        "participants": participants,
        "recent_transactions": recent_txs
    }

@app.get("/api/admin/rooms/{code}/investigate/{alias}")
def investigate_participant(code: str, alias: str, admin: dict = Depends(get_current_admin)):
    try:
        report = analyze_participant(code.strip().upper(), alias.strip())
        return report
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar auditoría: {str(e)}")

# --- PARTICIPANT ENDPOINTS ---

@app.post("/api/rooms/join")
def join_room(req: JoinRoomReq):
    code = req.room_code.strip().upper()
    alias = req.alias.strip()
    alias_norm = alias.upper()

    if not code or not alias:
        raise HTTPException(status_code=400, detail="Código de sala y alias son requeridos.")
    if len(alias) < 2 or len(alias) > 30:
        raise HTTPException(status_code=400, detail="El alias debe tener entre 2 y 30 caracteres.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms WHERE code = ?", (code,))
    room = cur.fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail=f"La sala '{code}' no existe.")
    if room["status"] != "OPEN":
        conn.close()
        raise HTTPException(status_code=403, detail="Esta sala se encuentra cerrada por el docente/administrador.")

    # Check if participant already exists in room
    cur.execute("SELECT * FROM participants WHERE room_code = ? AND alias_normalized = ?", (code, alias_norm))
    existing = cur.fetchone()

    now_iso = get_now_iso()
    if existing:
        # Existing participant: issue existing or refreshed session
        token = existing["session_token"]
        cur.execute("UPDATE participants SET last_active_at = ? WHERE id = ?", (now_iso, existing["id"]))
        conn.commit()
        part_data = dict(existing)
        conn.close()
        return {
            "token": token,
            "participant": part_data,
            "room": dict(room),
            "reconnected": True
        }
    else:
        # New participant registration
        part_id = f"usr_{uuid.uuid4().hex[:10]}"
        token = f"tok_{uuid.uuid4().hex}"
        init_bank = float(room["initial_bank_balance_cop"])

        cur.execute("""
            INSERT INTO participants (
                id, room_code, alias, alias_normalized, session_token,
                bank_balance_cop, wallet_cop, wallet_btc, wallet_eth, wallet_usdt, wallet_sol,
                created_at, last_active_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, 0.0, 0.0, 0.0, ?, ?)
        """, (part_id, code, alias, alias_norm, token, init_bank, now_iso, now_iso))

        # Log initial endowment transaction
        tx_id = f"TX-INIT-{uuid.uuid4().hex[:8].upper()}"
        tx_hash = generate_tx_hash(tx_id, "SISTEMA_CENTRAL", alias, "COP", init_bank, now_iso)
        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, 'DEPOSIT_INITIAL_ENDOWMENT', 'SISTEMA_CENTRAL', ?, 0, 'COP', ?, 0.0, 1.0, ?, ?, ?, 'CONFIRMED', 'Asignación de capital ficticio inicial', ?)
        """, (tx_id, code, alias, init_bank, init_bank, init_bank, tx_hash, now_iso))

        conn.commit()
        cur.execute("SELECT * FROM participants WHERE id = ?", (part_id,))
        created = dict(cur.fetchone())
        conn.close()

        return {
            "token": token,
            "participant": created,
            "room": dict(room),
            "reconnected": False
        }

@app.get("/api/participant/me")
def get_my_profile(part: dict = Depends(get_current_participant)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM participants WHERE id = ?", (part["id"],))
    fresh = dict(cur.fetchone())
    cur.execute("SELECT * FROM rooms WHERE code = ?", (fresh["room_code"],))
    room = dict(cur.fetchone())
    conn.close()
    return {"participant": fresh, "room": room}

@app.post("/api/participant/bank-transfer")
def bank_transfer(req: BankTransferReq, part: dict = Depends(get_current_participant)):
    amount = round_amount(req.amount, 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="El monto a transferir debe ser mayor a cero.")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute("SELECT * FROM participants WHERE id = ?", (part["id"],))
        p = cur.fetchone()
        
        bank_bal = Decimal(str(p["bank_balance_cop"]))
        wallet_bal = Decimal(str(p["wallet_cop"]))
        amt_dec = Decimal(str(amount))
        now_iso = get_now_iso()

        if req.action.upper() == "DEPOSIT":
            # Bank -> Wallet
            if bank_bal < amt_dec:
                raise HTTPException(status_code=400, detail=f"Saldo insuficiente en Banco. Tienes COP {bank_bal:,.2f}.")
            new_bank = float(bank_bal - amt_dec)
            new_wallet = float(wallet_bal + amt_dec)
            tx_type = "DEPOSIT_BANK_TO_WALLET"
            desc = "Traslado de fondos: Cuenta Bancaria -> Billetera COP"
        elif req.action.upper() == "WITHDRAW":
            # Wallet -> Bank
            if wallet_bal < amt_dec:
                raise HTTPException(status_code=400, detail=f"Saldo insuficiente en Billetera COP. Tienes COP {wallet_bal:,.2f}.")
            new_bank = float(bank_bal + amt_dec)
            new_wallet = float(wallet_bal - amt_dec)
            tx_type = "WITHDRAW_WALLET_TO_BANK"
            desc = "Traslado de fondos: Billetera COP -> Cuenta Bancaria"
        else:
            raise HTTPException(status_code=400, detail="Acción inválida. Usa DEPOSIT o WITHDRAW.")

        cur.execute("UPDATE participants SET bank_balance_cop = ?, wallet_cop = ? WHERE id = ?", (new_bank, new_wallet, p["id"]))

        tx_id = f"TX-BNK-{uuid.uuid4().hex[:8].upper()}"
        tx_hash = generate_tx_hash(tx_id, p["alias"], p["alias"], "COP", amount, now_iso)

        cur.execute("""
            INSERT INTO transactions (
                id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                tx_hash, status, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, 0, 'COP', ?, 0.0, 1.0, ?, ?, ?, 'CONFIRMED', ?, ?)
        """, (tx_id, p["room_code"], tx_type, p["alias"], p["alias"], amount, amount, amount, tx_hash, desc, now_iso))

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción bancaria: {str(e)}")
    finally:
        conn.close()

    return {"message": "Operación bancaria exitosa.", "new_bank_balance": new_bank, "new_wallet_cop": new_wallet}

@app.post("/api/participant/trade")
async def execute_trade(req: TradeReq, part: dict = Depends(get_current_participant)):
    side = req.side.upper()
    asset = req.asset.upper()

    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="El tipo de operación debe ser BUY o SELL.")
    if asset not in ("BTC", "ETH", "USDT", "SOL"):
        raise HTTPException(status_code=400, detail="Activo no soportado. Debe ser BTC, ETH, USDT o SOL.")
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a cero.")

    # Get verified market replay price
    engine = MarketReplayEngine.get_instance()
    replay_state = engine.get_state()
    current_replay_prices = replay_state["prices"]

    if asset not in current_replay_prices or current_replay_prices[asset] <= 0:
        raise HTTPException(status_code=503, detail=f"Cotización histórica no disponible actualmente para {asset}.")

    unit_price = Decimal(str(current_replay_prices[asset]))
    FEE_RATE = Decimal("0.002") # 0.2% commission

    # Calculate exact amounts
    if side == "BUY":
        if req.quote_type.upper() == "COP":
            gross_cop = Decimal(str(req.amount))
            fee_cop = (gross_cop * FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_cop_needed = gross_cop + fee_cop
            crypto_amount = (gross_cop / unit_price).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        else: # CRYPTO
            crypto_amount = Decimal(str(req.amount)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
            gross_cop = (crypto_amount * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            fee_cop = (gross_cop * FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_cop_needed = gross_cop + fee_cop
    else: # SELL
        crypto_amount = Decimal(str(req.amount)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        gross_cop = (crypto_amount * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fee_cop = (gross_cop * FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net_cop_received = gross_cop - fee_cop

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute("SELECT * FROM participants WHERE id = ?", (part["id"],))
        p = cur.fetchone()
        
        wallet_cop = Decimal(str(p["wallet_cop"]))
        wallet_col_name = f"wallet_{asset.lower()}"
        wallet_crypto = Decimal(str(p[wallet_col_name]))
        now_iso = get_now_iso()

        meta_dict = {
            "description": f"Orden de {side} en Market Replay a tasa COP {float(unit_price):,.2f} por {asset}",
            "simulated_market_datetime_cot": replay_state.get("simulated_datetime_cot_iso", ""),
            "simulated_market_datetime_utc": replay_state.get("simulated_datetime_utc_iso", ""),
            "dataset_id": replay_state.get("dataset_id", "HIST_20261110_COT"),
            "price_nature": replay_state.get("price_type", "OBSERVADO_REAL"),
            "price_usd_raw": replay_state.get("prices_usd_raw", {}).get(asset, 0.0),
            "exchange_rate_applied": replay_state.get("exchange_rate_documentation", {}),
            "replay_speed": replay_state.get("speed", 33.82),
            "market_mode": "HISTORICAL_REPLAY"
        }
        tx_meta = json.dumps(meta_dict, ensure_ascii=False)

        if side == "BUY":
            if wallet_cop < total_cop_needed:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Saldo insuficiente en Billetera COP. Requieres COP {total_cop_needed:,.2f} (incluyendo 0.2% comisión COP {fee_cop:,.2f}), pero tienes COP {wallet_cop:,.2f}."
                )
            new_wallet_cop = float(wallet_cop - total_cop_needed)
            new_wallet_crypto = float(wallet_crypto + crypto_amount)
            net_cop = float(gross_cop)

            cur.execute(f"UPDATE participants SET wallet_cop = ?, {wallet_col_name} = ? WHERE id = ?", (new_wallet_cop, new_wallet_crypto, p["id"]))

            tx_id = f"TX-BUY-{uuid.uuid4().hex[:8].upper()}"
            tx_hash = generate_tx_hash(tx_id, p["alias"], "MERCADO_SIMULADO", asset, float(crypto_amount), now_iso)
            
            cur.execute("""
                INSERT INTO transactions (
                    id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                    asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                    tx_hash, status, metadata, created_at
                ) VALUES (?, ?, 'BUY_CRYPTO', ?, 'MERCADO_SIMULADO', 0, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?)
            """, (
                tx_id, p["room_code"], p["alias"], asset, float(crypto_amount),
                float(fee_cop), float(unit_price), float(gross_cop), net_cop,
                tx_hash, tx_meta, now_iso
            ))

        else: # SELL
            if wallet_crypto < crypto_amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Saldo insuficiente en {asset}. Intentas vender {float(crypto_amount)} {asset}, pero dispones de {float(wallet_crypto)} {asset}."
                )
            new_wallet_cop = float(wallet_cop + net_cop_received)
            new_wallet_crypto = float(wallet_crypto - crypto_amount)

            cur.execute(f"UPDATE participants SET wallet_cop = ?, {wallet_col_name} = ? WHERE id = ?", (new_wallet_cop, new_wallet_crypto, p["id"]))

            tx_id = f"TX-SEL-{uuid.uuid4().hex[:8].upper()}"
            tx_hash = generate_tx_hash(tx_id, p["alias"], "MERCADO_SIMULADO", asset, float(crypto_amount), now_iso)

            cur.execute("""
                INSERT INTO transactions (
                    id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                    asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                    tx_hash, status, metadata, created_at
                ) VALUES (?, ?, 'SELL_CRYPTO', ?, 'MERCADO_SIMULADO', 0, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?)
            """, (
                tx_id, p["room_code"], p["alias"], asset, float(crypto_amount),
                float(fee_cop), float(unit_price), float(gross_cop), float(net_cop_received),
                tx_hash, tx_meta, now_iso
            ))

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al ejecutar orden de mercado: {str(e)}")
    finally:
        conn.close()

    return {
        "message": f"Orden de {side} ejecutada con éxito.",
        "side": side,
        "asset": asset,
        "amount": float(crypto_amount),
        "unit_price_cop": float(unit_price),
        "gross_amount_cop": float(gross_cop),
        "fee_cop": float(fee_cop),
        "new_wallet_cop": new_wallet_cop,
        "new_wallet_crypto": new_wallet_crypto
    }

@app.post("/api/participant/transfer")
def transfer_funds(req: TransferReq, part: dict = Depends(get_current_participant)):
    t_type = req.transfer_type.upper()
    asset = req.asset.upper()

    if t_type not in ("INTERNAL", "EXTERNAL"):
        raise HTTPException(status_code=400, detail="El tipo de transferencia debe ser INTERNAL o EXTERNAL.")
    if asset not in ("COP", "BTC", "ETH", "USDT", "SOL"):
        raise HTTPException(status_code=400, detail="Activo inválido.")
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto a transferir debe ser mayor a cero.")

    col_name = "wallet_cop" if asset == "COP" else f"wallet_{asset.lower()}"
    amt_dec = Decimal(str(req.amount))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute("SELECT * FROM participants WHERE id = ?", (part["id"],))
        sender = cur.fetchone()
        
        sender_bal = Decimal(str(sender[col_name]))
        if sender_bal < amt_dec:
            raise HTTPException(
                status_code=400,
                detail=f"Saldo insuficiente en {asset}. Dispones de {float(sender_bal)} {asset}."
            )

        now_iso = get_now_iso()

        if t_type == "INTERNAL":
            if not req.destination_alias:
                raise HTTPException(status_code=400, detail="Debes indicar el alias de destino.")
            dest_alias = req.destination_alias.strip()
            dest_norm = dest_alias.upper()

            if dest_norm == sender["alias_normalized"]:
                raise HTTPException(status_code=400, detail="No puedes transferirte a ti mismo.")

            cur.execute("SELECT * FROM participants WHERE room_code = ? AND alias_normalized = ?", (sender["room_code"], dest_norm))
            receiver = cur.fetchone()
            if not receiver:
                raise HTTPException(status_code=404, detail=f"El participante '{dest_alias}' no existe en esta sala.")

            receiver_bal = Decimal(str(receiver[col_name]))

            # Atomic update
            cur.execute(f"UPDATE participants SET {col_name} = ? WHERE id = ?", (float(sender_bal - amt_dec), sender["id"]))
            cur.execute(f"UPDATE participants SET {col_name} = ? WHERE id = ?", (float(receiver_bal + amt_dec), receiver["id"]))

            tx_id = f"TX-INT-{uuid.uuid4().hex[:8].upper()}"
            tx_hash = generate_tx_hash(tx_id, sender["alias"], receiver["alias"], asset, float(amt_dec), now_iso)

            cur.execute("""
                INSERT INTO transactions (
                    id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                    asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                    tx_hash, status, metadata, created_at
                ) VALUES (?, ?, 'TRANSFER_INTERNAL', ?, ?, 0, ?, ?, 0.0, NULL, NULL, NULL, ?, 'CONFIRMED', ?, ?)
            """, (tx_id, sender["room_code"], sender["alias"], receiver["alias"], asset, float(amt_dec), tx_hash, req.notes or "Transferencia interna P2P", now_iso))

            dest_display = receiver["alias"]

        else: # EXTERNAL
            if not req.external_address:
                raise HTTPException(status_code=400, detail="Debes ingresar una dirección externa simulada (ej. 0x...).")
            ext_addr = req.external_address.strip()
            if len(ext_addr) < 8:
                raise HTTPException(status_code=400, detail="La dirección externa debe tener al menos 8 caracteres.")

            # Debit sender wallet
            cur.execute(f"UPDATE participants SET {col_name} = ? WHERE id = ?", (float(sender_bal - amt_dec), sender["id"]))

            tx_id = f"TX-EXT-{uuid.uuid4().hex[:8].upper()}"
            tx_hash = generate_tx_hash(tx_id, sender["alias"], ext_addr, asset, float(amt_dec), now_iso)

            cur.execute("""
                INSERT INTO transactions (
                    id, room_code, tx_type, sender_alias, receiver_alias, is_external,
                    asset, amount, fee_cop, unit_price_cop, gross_amount_cop, net_amount_cop,
                    tx_hash, status, metadata, created_at
                ) VALUES (?, ?, 'TRANSFER_EXTERNAL', ?, ?, 1, ?, ?, 0.0, NULL, NULL, NULL, ?, 'CONFIRMED', ?, ?)
            """, (tx_id, sender["room_code"], sender["alias"], ext_addr, asset, float(amt_dec), tx_hash, f"Transferencia hacia dirección externa: {ext_addr}. Fin de visibilidad interna.", now_iso))

            dest_display = ext_addr

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al procesar la transferencia: {str(e)}")
    finally:
        conn.close()

    return {
        "message": "Transferencia ejecutada con éxito.",
        "type": t_type,
        "asset": asset,
        "amount": float(amt_dec),
        "destination": dest_display,
        "tx_hash": tx_hash
    }

@app.get("/api/participant/history")
def get_my_history(part: dict = Depends(get_current_participant)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM transactions 
        WHERE room_code = ? AND (sender_alias = ? OR receiver_alias = ?)
        ORDER BY created_at DESC
    """, (part["room_code"], part["alias"], part["alias"]))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"transactions": rows}

@app.get("/api/participant/room-peers")
def get_room_peers(part: dict = Depends(get_current_participant)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT alias FROM participants 
        WHERE room_code = ? AND id != ?
        ORDER BY alias ASC
    """, (part["room_code"], part["id"]))
    peers = [r["alias"] for r in cur.fetchall()]
    conn.close()
    return {"peers": peers}

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
def serve_admin():
    with open("static/admin.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    lan_ip = get_lan_ip()
    print("=" * 65)
    print("           CRYPTO LAB - SIMULADOR & AUDITORIA FORENSE")
    print("=" * 65)
    print(f" -> Servidor escuchando en: http://0.0.0.0:{port}")
    print(f" -> Acceso local (esta PC): http://localhost:{port}")
    print(f" -> Acceso celular (Misma Wi-Fi): http://{lan_ip}:{port}")
    admin_u, _ = get_admin_credentials()
    print(f" -> Panel Administrador: http://localhost:{port}/admin")
    print(f" -> Usuario Administrador: {admin_u}")
    print(f" -> Contraseña: [PROTEGIDA - Configurada en archivo .env]")
    print("=" * 65)
    uvicorn.run(app, host="0.0.0.0", port=port)
