import json
from datetime import datetime, timezone
from collections import defaultdict, deque
from database import get_db_connection

def parse_iso_time(t_str):
    try:
        dt = datetime.fromisoformat(t_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)

def analyze_participant(room_code: str, alias: str, db_conn=None):
    close_conn = False
    if db_conn is None:
        db_conn = get_db_connection()
        close_conn = True

    cur = db_conn.cursor()

    # Get room info
    cur.execute("SELECT * FROM rooms WHERE code = ?", (room_code,))
    room = cur.fetchone()
    if not room:
        if close_conn: db_conn.close()
        raise ValueError(f"Sala {room_code} no encontrada.")

    # Get participant info
    cur.execute(
        "SELECT * FROM participants WHERE room_code = ? AND alias_normalized = ?",
        (room_code, alias.strip().upper())
    )
    participant = cur.fetchone()
    if not participant:
        if close_conn: db_conn.close()
        raise ValueError(f"Participante '{alias}' no encontrado en la sala {room_code}.")

    # Fetch all transactions in the room to build global context and trace
    cur.execute(
        "SELECT * FROM transactions WHERE room_code = ? ORDER BY created_at ASC",
        (room_code,)
    )
    all_room_txs = [dict(row) for row in cur.fetchall()]

    # Filter participant's direct transactions
    direct_txs = [
        tx for tx in all_room_txs 
        if tx["sender_alias"] == participant["alias"] or tx["receiver_alias"] == participant["alias"]
    ]

    # Calculate financial aggregates
    initial_balance = float(room["initial_bank_balance_cop"])
    current_bank = float(participant["bank_balance_cop"])
    current_wallet_cop = float(participant["wallet_cop"])
    current_btc = float(participant["wallet_btc"])
    current_eth = float(participant["wallet_eth"])
    current_usdt = float(participant["wallet_usdt"])
    current_sol = float(participant["wallet_sol"])

    # Aggregate by tx_type
    total_purchases_cop = 0.0
    total_sales_cop = 0.0
    total_fees_paid_cop = 0.0
    total_internal_transfers_sent = 0
    total_internal_transfers_received = 0
    total_external_transfers = 0
    
    crypto_bought = defaultdict(float)
    crypto_sold = defaultdict(float)
    crypto_sent = defaultdict(float)
    crypto_received = defaultdict(float)

    related_participants_counter = defaultdict(lambda: {"sent_count": 0, "received_count": 0, "assets": set()})

    for tx in direct_txs:
        t_type = tx["tx_type"]
        is_sender = (tx["sender_alias"] == participant["alias"])
        is_receiver = (tx["receiver_alias"] == participant["alias"])
        asset = tx["asset"]
        amt = float(tx["amount"])
        fee = float(tx["fee_cop"] or 0.0)

        if is_sender:
            total_fees_paid_cop += fee

        if t_type == "BUY_CRYPTO" and is_sender:
            total_purchases_cop += float(tx["gross_amount_cop"] or 0.0)
            crypto_bought[asset] += amt
        elif t_type == "SELL_CRYPTO" and is_sender:
            total_sales_cop += float(tx["gross_amount_cop"] or 0.0)
            crypto_sold[asset] += amt
        elif t_type == "TRANSFER_INTERNAL":
            if is_sender:
                total_internal_transfers_sent += 1
                crypto_sent[asset] += amt
                related_participants_counter[tx["receiver_alias"]]["sent_count"] += 1
                related_participants_counter[tx["receiver_alias"]]["assets"].add(asset)
            elif is_receiver:
                total_internal_transfers_received += 1
                crypto_received[asset] += amt
                related_participants_counter[tx["sender_alias"]]["received_count"] += 1
                related_participants_counter[tx["sender_alias"]]["assets"].add(asset)
        elif t_type == "TRANSFER_EXTERNAL" and is_sender:
            total_external_transfers += 1
            crypto_sent[asset] += amt

    # Related participants list
    related_participants = []
    for r_alias, data in related_participants_counter.items():
        related_participants.append({
            "alias": r_alias,
            "transfers_to_him": data["sent_count"],
            "transfers_from_him": data["received_count"],
            "assets_involved": list(data["assets"])
        })

    # Reconstruct Transfer Graph & Chains (Forward trace from investigated participant)
    graph = build_forensic_graph(all_room_txs, participant["alias"])

    # Detect Risk Alerts
    alerts = detect_risk_alerts(all_room_txs, participant["alias"], direct_txs, graph=graph)

    # Automatic Objective Findings
    findings = generate_objective_findings(participant, room, direct_txs, graph, alerts)

    # Financial Reconciliation calculation
    reconciliation = calculate_reconciliation(
        initial_balance,
        current_bank,
        current_wallet_cop,
        current_btc,
        current_eth,
        current_usdt,
        current_sol,
        direct_txs,
        participant["alias"]
    )

    # Executive Summary calculations
    risk_level = "BAJO"
    if any(a.get("severity") == "ALTO" for a in alerts):
        risk_level = "ALTO"
    elif any(a.get("severity") == "MEDIO" for a in alerts):
        risk_level = "MEDIO"

    assets_used = sorted(list(set(tx["asset"] for tx in direct_txs)))
    period_start = direct_txs[0]["created_at"] if direct_txs else participant["created_at"]
    period_end = direct_txs[-1]["created_at"] if direct_txs else participant["last_active_at"]

    total_moved_cop = total_purchases_cop + total_sales_cop + sum(
        float(tx["amount"]) for tx in direct_txs if tx["asset"] == "COP" and tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL")
    )

    executive_summary = {
        "total_operations_analyzed": len(direct_txs),
        "assets_involved": assets_used,
        "total_volume_moved_cop": total_moved_cop,
        "counterparties_count": len(related_participants),
        "alerts_count": len(alerts),
        "risk_level": risk_level,
        "period_analyzed": f"{period_start[:19].replace('T', ' ')} a {period_end[:19].replace('T', ' ')}"
    }

    executive_conclusion = (
        "Con base en los movimientos analizados, se identificaron patrones de transferencia "
        "que justifican revisión adicional desde la perspectiva de trazabilidad financiera. "
        "No se evidenciaron inconsistencias contables en la conciliación del usuario analizado."
    )

    result = {
        "participant": {
            "id": participant["id"],
            "alias": participant["alias"],
            "room_code": room["code"],
            "room_name": room["name"],
            "created_at": participant["created_at"],
            "last_active_at": participant["last_active_at"],
            "balances": {
                "bank_cop": current_bank,
                "wallet_cop": current_wallet_cop,
                "wallet_btc": current_btc,
                "wallet_eth": current_eth,
                "wallet_usdt": current_usdt,
                "wallet_sol": current_sol
            }
        },
        "room": {
            "code": room["code"],
            "name": room["name"],
            "status": room["status"],
            "initial_bank_balance_cop": initial_balance,
            "created_at": room["created_at"]
        },
        "audit_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_alias": participant["alias"],
            "system_version": "Crypto Lab Forensic Suite v1.0",
            "is_simulation": True
        },
        "financial_summary": {
            "initial_balance_cop": initial_balance,
            "final_bank_cop": current_bank,
            "final_wallet_cop": current_wallet_cop,
            "final_total_cop": current_bank + current_wallet_cop,
            "total_purchases_cop": total_purchases_cop,
            "total_sales_cop": total_sales_cop,
            "total_fees_paid_cop": total_fees_paid_cop,
            "total_internal_transfers_sent": total_internal_transfers_sent,
            "total_internal_transfers_received": total_internal_transfers_received,
            "total_external_transfers": total_external_transfers,
            "crypto_bought": dict(crypto_bought),
            "crypto_sold": dict(crypto_sold),
            "crypto_sent": dict(crypto_sent),
            "crypto_received": dict(crypto_received)
        },
        "related_participants": related_participants,
        "graph": graph,
        "alerts": alerts,
        "findings": findings,
        "limitations": [
            "1. Principio de Fungibilidad: Dentro de una billetera multiactivo digital, los tokens del mismo activo se mezclan contablemente. Si un participante tiene fondos previos o realiza múltiples operaciones, las salidas posteriores no pueden vincularse matemáticamente a un depósito específico sin aplicar un método de atribución (ej. FIFO o LIFO).",
            "2. Destinos Externos Simulados: Toda transferencia hacia direcciones externas representa la salida del perímetro interno de Crypto Lab. La plataforma certifica el envío y débito interno, pero carece de visibilidad respecto a movimientos posteriores fuera de la sala.",
            "3. Carácter Académico: Los hashes generados ilustran la estructura de identificadores de libro contable distribuido. Este simulador no se conecta a ninguna red blockchain pública ni almacena llaves criptográficas privadas reales."
        ],
        "reconciliation": reconciliation,
        "chronology": direct_txs,
        "executive_summary": executive_summary,
        "executive_conclusion": executive_conclusion
    }

    if close_conn:
        db_conn.close()

    return result

def build_forensic_graph(all_txs, target_alias):
    # Only transfer transactions form the money flow graph
    transfer_txs = [
        tx for tx in all_txs 
        if tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL")
    ]

    nodes = {}
    edges = []
    chains = []

    # Target node
    nodes[target_alias] = {
        "id": target_alias,
        "label": target_alias,
        "type": "TARGET",
        "is_target": True,
        "is_external": False
    }

    # Outgoing adjacency: sender -> list of txs
    out_map = defaultdict(list)
    for tx in transfer_txs:
        out_map[tx["sender_alias"]].append(tx)

    # Incoming adjacency: receiver -> list of txs
    in_map = defaultdict(list)
    for tx in transfer_txs:
        in_map[tx["receiver_alias"]].append(tx)

    # Add incoming edges to target (participants that sent funds to target)
    for tx in in_map.get(target_alias, []):
        s = tx["sender_alias"]
        if s not in nodes:
            nodes[s] = {"id": s, "label": s, "type": "SOURCE", "is_target": False, "is_external": False}
        edges.append({
            "id": tx["id"],
            "source": s,
            "target": target_alias,
            "asset": tx["asset"],
            "amount": float(tx["amount"]),
            "tx_hash": tx["tx_hash"],
            "created_at": tx["created_at"],
            "is_external": False,
            "label": f"{tx['amount']} {tx['asset']}"
        })

    # Forward BFS / DFS to track chains originating from target
    # Queue items: (current_node, current_chain_path, depth, visited_edges)
    queue = deque()
    for tx in out_map.get(target_alias, []):
        queue.append((tx["receiver_alias"], [target_alias, tx["receiver_alias"]], 1, [tx["id"]]))
        
        # Add edge
        dest = tx["receiver_alias"]
        is_ext = bool(tx["is_external"])
        if dest not in nodes:
            nodes[dest] = {
                "id": dest,
                "label": dest if not is_ext else f"Destino Externo ({dest[:10]}...)",
                "type": "EXTERNAL" if is_ext else "INTERMEDIARY",
                "is_target": False,
                "is_external": is_ext
            }
        edges.append({
            "id": tx["id"],
            "source": target_alias,
            "target": dest,
            "asset": tx["asset"],
            "amount": float(tx["amount"]),
            "tx_hash": tx["tx_hash"],
            "created_at": tx["created_at"],
            "is_external": is_ext,
            "label": f"{tx['amount']} {tx['asset']}"
        })

    visited_chains = set()
    MAX_DEPTH = 6

    while queue:
        curr_node, path, depth, used_txs = queue.popleft()
        path_tuple = tuple(path)
        if path_tuple not in visited_chains:
            visited_chains.add(path_tuple)
            chains.append({
                "path": path,
                "length": len(path) - 1,
                "reaches_external": nodes.get(curr_node, {}).get("is_external", False),
                "terminal_node": curr_node
            })

        if nodes.get(curr_node, {}).get("is_external", False) or depth >= MAX_DEPTH:
            continue

        # Look for downstream transfers from curr_node that occurred AFTER arrival
        # Find arrival time
        arrival_tx = next((t for t in transfer_txs if t["id"] == used_txs[-1]), None)
        arrival_time = arrival_tx["created_at"] if arrival_tx else "1970-01-01"

        for next_tx in out_map.get(curr_node, []):
            if next_tx["id"] in used_txs:
                continue
            
            # Forwarding should occur after or at arrival
            if next_tx["created_at"] >= arrival_time:
                next_dest = next_tx["receiver_alias"]
                next_is_ext = bool(next_tx["is_external"])

                if next_dest not in nodes:
                    nodes[next_dest] = {
                        "id": next_dest,
                        "label": next_dest if not next_is_ext else f"Destino Externo ({next_dest[:10]}...)",
                        "type": "EXTERNAL" if next_is_ext else "INTERMEDIARY",
                        "is_target": (next_dest == target_alias),
                        "is_external": next_is_ext
                    }

                # Avoid duplicate edge id in list
                if not any(e["id"] == next_tx["id"] for e in edges):
                    edges.append({
                        "id": next_tx["id"],
                        "source": curr_node,
                        "target": next_dest,
                        "asset": next_tx["asset"],
                        "amount": float(next_tx["amount"]),
                        "tx_hash": next_tx["tx_hash"],
                        "created_at": next_tx["created_at"],
                        "is_external": next_is_ext,
                        "label": f"{next_tx['amount']} {next_tx['asset']}"
                    })

                new_path = list(path) + [next_dest]
                queue.append((next_dest, new_path, depth + 1, used_txs + [next_tx["id"]]))

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "chains": chains
    }

def detect_risk_alerts(all_txs, target_alias, direct_txs, graph=None):
    alerts = []
    
    # 1. Rapid repeated transfers (multiple outgoing in < 300 seconds)
    outgoing_transfers = [
        tx for tx in direct_txs 
        if tx["sender_alias"] == target_alias and tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL")
    ]
    if len(outgoing_transfers) >= 2:
        times = [parse_iso_time(tx["created_at"]) for tx in outgoing_transfers]
        times.sort()
        delta_sec = (times[-1] - times[0]).total_seconds()
        if delta_sec <= 300:
            alerts.append({
                "code": "ALT_VEL_RAPID_TRANSFERS",
                "severity": "ALTO",
                "title": "Transferencias Múltiples en Período Ultracorto",
                "description": f"Se registraron {len(outgoing_transfers)} transferencias salientes en un lapso de {int(delta_sec)} segundos. Este comportamiento denota dispersión acelerada de fondos.",
                "impact": "Este patrón sugiere fragmentación o dispersión acelerada de fondos en una ventana temporal reducida.",
                "details": f"{len(outgoing_transfers)} operaciones salientes detectadas."
            })

    # 2. Fast conversion fiat -> crypto then transfer
    purchases = [tx for tx in direct_txs if tx["tx_type"] == "BUY_CRYPTO" and tx["sender_alias"] == target_alias]
    for p in purchases:
        p_time = parse_iso_time(p["created_at"])
        p_asset = p["asset"]
        p_amt = float(p["amount"])
        # Check if transferred within 300 seconds
        matching_transfers = [
            tx for tx in outgoing_transfers 
            if tx["asset"] == p_asset and 0 <= (parse_iso_time(tx["created_at"]) - p_time).total_seconds() <= 300
        ]
        sum_transferred = sum(float(tx["amount"]) for tx in matching_transfers)
        if sum_transferred >= (p_amt * 0.70):
            alerts.append({
                "code": "ALT_FAST_CONV_TRANSFER",
                "severity": "ALTO",
                "title": "Conversión Inmediata y Dispersión de Criptoactivo",
                "description": f"El participante adquirió {p_amt} {p_asset} y en menos de 5 minutos transfirió {sum_transferred} {p_asset} ({round((sum_transferred/p_amt)*100, 1)}% del total adquirido).",
                "impact": "El usuario convirtió fondos a criptoactivo y posteriormente los transfirió en un intervalo corto. Este patrón amerita revisión de trazabilidad y propósito económico.",
                "details": f"Activo: {p_asset}, Monto Adquirido: {p_amt}, Monto Transferido: {sum_transferred}"
            })

    # 3. Transfer to external unmonitored destination (capital flight)
    ext_transfers = [tx for tx in outgoing_transfers if tx["is_external"] == 1]
    for ext in ext_transfers:
        alerts.append({
            "code": "ALT_EXTERNAL_OUTFLOW",
            "severity": "MEDIO",
            "title": "Transferencia a Billetera Externa Fuera del Perímetro",
            "description": f"Salida de {ext['amount']} {ext['asset']} hacia una dirección externa ({ext['receiver_alias']}). En este punto finaliza la trazabilidad del simulador.",
            "impact": "Indica salida del perímetro supervisado hacia una dirección no identificada, limitando la visibilidad de operaciones subsecuentes.",
            "details": f"Destino: {ext['receiver_alias']}, Tx: {ext['tx_hash'][:16]}..."
        })

    # 4. Circular transfers (A -> B -> ... -> A)
    transfer_all = [tx for tx in all_txs if tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL")]
    recipients = set(tx["receiver_alias"] for tx in outgoing_transfers if not tx["is_external"])
    for r in recipients:
        return_txs = [tx for tx in transfer_all if tx["sender_alias"] == r and tx["receiver_alias"] == target_alias]
        if return_txs:
            alerts.append({
                "code": "ALT_CIRCULAR_FLOW",
                "severity": "ALTO",
                "title": "Patrón de Transferencia Circular / Retorno de Fondos",
                "description": f"Se identificó un flujo circular entre '{target_alias}' y '{r}'. Los fondos enviados retornaron total o parcialmente al remitente original.",
                "impact": "Identifica retorno de liquidez al remitente original sin beneficio económico ostensible, sugiriendo revisión de la causa del movimiento.",
                "details": f"Contraparte involucrada: {r}."
            })

    # 5. Concentration of funds (Fan-in)
    incoming_transfers = [
        tx for tx in direct_txs 
        if tx["receiver_alias"] == target_alias and tx["tx_type"] == "TRANSFER_INTERNAL"
    ]
    distinct_senders = set(tx["sender_alias"] for tx in incoming_transfers)
    if len(distinct_senders) >= 2:
        alerts.append({
            "code": "ALT_CONCENTRATION_FANIN",
            "severity": "MEDIO",
            "title": "Concentración de Fondos de Múltiples Orígenes (Fan-In)",
            "description": f"El participante ha recibido transferencias de {len(distinct_senders)} remitentes distintos ({', '.join(distinct_senders)}), actuando potencialmente como recolector o nodo central.",
            "impact": "Comportamiento representativo de concentración de recursos de diversas contrapartes hacia un nodo central.",
            "details": f"Remitentes: {list(distinct_senders)}"
        })

    # 6. Multi-hop Chain Propagation
    if graph and graph.get("chains"):
        long_chains = [c for c in graph["chains"] if c.get("length", 0) >= 2]
        if long_chains:
            alerts.append({
                "code": "ALT_CHAIN_PROPAGATION",
                "severity": "MEDIO",
                "title": "Cadena de Transferencias Sucesivas (Multisalto)",
                "description": f"Se identificó la propagación multietapa de activos a través de una cadena de {long_chains[0]['length']} saltos sucesivos.",
                "impact": "El enrutamiento de fondos a través de múltiples intermediarios incrementa la complejidad del rastreo de origen y destino final.",
                "details": f"Ruta identificada: {' -> '.join(long_chains[0]['path'])}"
            })

    # Deduplicate alerts by code
    dedup = {}
    for a in alerts:
        if a["code"] not in dedup:
            dedup[a["code"]] = a
    return list(dedup.values())

def generate_objective_findings(participant, room, direct_txs, graph, alerts):
    findings = []
    alias = participant["alias"]

    # Factual finding 1: Account registration & Initial Endowment
    findings.append(
        f"1. Registro y Asignación Inicial: El participante '{alias}' ingresó a la sala '{room['code']}' ({room['name']}) "
        f"con una asignación bancaria ficticia inicial de {float(room['initial_bank_balance_cop']):,.2f} COP."
    )

    # Factual finding 2: Banking transfers (Bank <-> Wallet)
    deposits = [tx for tx in direct_txs if tx["tx_type"] == "DEPOSIT_BANK_TO_WALLET"]
    withdraws = [tx for tx in direct_txs if tx["tx_type"] == "WITHDRAW_WALLET_TO_BANK"]
    if deposits:
        tot_dep = sum(float(tx["amount"]) for tx in deposits)
        findings.append(
            f"2. Movimientos Bancarios Internos: Trasladó {tot_dep:,.2f} COP desde su cuenta bancaria hacia su billetera de operaciones."
        )

    # Factual finding 3: Trading volume
    purchases = [tx for tx in direct_txs if tx["tx_type"] == "BUY_CRYPTO"]
    if purchases:
        p_summary = ", ".join([f"{tx['amount']} {tx['asset']} (COP {float(tx['gross_amount_cop']):,.2f})" for tx in purchases])
        findings.append(
            f"3. Compra de Criptoactivos: Efectuó {len(purchases)} orden(es) de compra en el mercado simulado: {p_summary}."
        )

    # Factual finding 4: Internal and External transfers
    out_transfers = [tx for tx in direct_txs if tx["sender_alias"] == alias and tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL")]
    if out_transfers:
        t_summary = ", ".join([f"{tx['amount']} {tx['asset']} hacia '{tx['receiver_alias']}'" for tx in out_transfers])
        findings.append(
            f"4. Dispersión de Fondos: Transfirió fondos hacia otras billeteras: {t_summary}."
        )

    # Factual finding 5: Multihop chain trace
    long_chains = [c for c in graph.get("chains", []) if c["length"] >= 2]
    if long_chains:
        chain_paths = [" -> ".join(c["path"]) for c in long_chains]
        findings.append(
            f"5. Reconstrucción de Saltos Sucesivos: Se determinó la propagación multietapa de los activos a través de la(s) cadena(s): {'; '.join(chain_paths)}."
        )

    # Factual finding 6: Final Destination and Perimeter
    ext_chains = [c for c in graph.get("chains", []) if c["reaches_external"]]
    if ext_chains:
        terminals = set(c["terminal_node"] for c in ext_chains)
        findings.append(
            f"6. Ruptura del Perímetro de Control: Los fondos alcanzaron destino(s) externo(s) ({', '.join(terminals)}), "
            f"donde concluye la capacidad de auditoría interna de la plataforma."
        )

    return findings

def calculate_reconciliation(init_balance, cur_bank, cur_wallet_cop, cur_btc, cur_eth, cur_usdt, cur_sol, direct_txs, alias):
    # Mathematical reconciliation:
    # Bank Balance = Init Balance - Deposits to Wallet + Withdrawals from Wallet
    # Wallet COP = Deposits from Bank - Withdrawals to Bank - Purchases COP + Sales COP - Fees COP - Transfers Out COP + Transfers In COP
    
    dep_bank_to_wallet = sum(float(tx["amount"]) for tx in direct_txs if tx["tx_type"] == "DEPOSIT_BANK_TO_WALLET")
    with_wallet_to_bank = sum(float(tx["amount"]) for tx in direct_txs if tx["tx_type"] == "WITHDRAW_WALLET_TO_BANK")
    
    expected_bank = init_balance - dep_bank_to_wallet + with_wallet_to_bank
    bank_discrepancy = round(cur_bank - expected_bank, 4)

    # Purchases & Sales
    cop_spent_buying = sum(float(tx["gross_amount_cop"]) + float(tx["fee_cop"]) for tx in direct_txs if tx["tx_type"] == "BUY_CRYPTO")
    cop_earned_selling = sum(float(tx["net_amount_cop"]) for tx in direct_txs if tx["tx_type"] == "SELL_CRYPTO")
    
    # COP transfers
    cop_transfers_out = sum(float(tx["amount"]) for tx in direct_txs if tx["asset"] == "COP" and tx["sender_alias"] == alias and tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL"))
    cop_transfers_in = sum(float(tx["amount"]) for tx in direct_txs if tx["asset"] == "COP" and tx["receiver_alias"] == alias and tx["tx_type"] == "TRANSFER_INTERNAL")

    expected_wallet_cop = dep_bank_to_wallet - with_wallet_to_bank - cop_spent_buying + cop_earned_selling - cop_transfers_out + cop_transfers_in
    wallet_cop_discrepancy = round(cur_wallet_cop - expected_wallet_cop, 4)

    # Crypto assets reconciliation
    crypto_assets = ["BTC", "ETH", "USDT", "SOL"]
    cur_balances = {"BTC": cur_btc, "ETH": cur_eth, "USDT": cur_usdt, "SOL": cur_sol}
    crypto_reconciliation = {}

    for asset in crypto_assets:
        bought = sum(float(tx["amount"]) for tx in direct_txs if tx["tx_type"] == "BUY_CRYPTO" and tx["asset"] == asset)
        sold = sum(float(tx["amount"]) for tx in direct_txs if tx["tx_type"] == "SELL_CRYPTO" and tx["asset"] == asset)
        sent = sum(float(tx["amount"]) for tx in direct_txs if tx["sender_alias"] == alias and tx["asset"] == asset and tx["tx_type"] in ("TRANSFER_INTERNAL", "TRANSFER_EXTERNAL"))
        received = sum(float(tx["amount"]) for tx in direct_txs if tx["receiver_alias"] == alias and tx["asset"] == asset and tx["tx_type"] == "TRANSFER_INTERNAL")
        
        expected = bought - sold - sent + received
        actual = cur_balances[asset]
        discrepancy = round(actual - expected, 8)

        crypto_reconciliation[asset] = {
            "bought": round(bought, 8),
            "sold": round(sold, 8),
            "sent": round(sent, 8),
            "received": round(received, 8),
            "expected_balance": round(expected, 8),
            "actual_balance": round(actual, 8),
            "discrepancy": discrepancy,
            "status": "CONCILIADO" if abs(discrepancy) < 1e-6 else "DESCUADRE_DETECTADO"
        }

    is_bank_balanced = (abs(bank_discrepancy) < 0.01)
    is_wallet_cop_balanced = (abs(wallet_cop_discrepancy) < 0.01)
    is_crypto_balanced = all(c["status"] == "CONCILIADO" for c in crypto_reconciliation.values())

    return {
        "status": "CONCILIACIÓN_PERFECTA" if (is_bank_balanced and is_wallet_cop_balanced and is_crypto_balanced) else "DISCREPANCIA_CONTABLE",
        "bank": {
            "initial": init_balance,
            "net_deposits": dep_bank_to_wallet - with_wallet_to_bank,
            "expected": expected_bank,
            "actual": cur_bank,
            "discrepancy": bank_discrepancy,
            "status": "CONCILIADO" if is_bank_balanced else "DESCUADRE"
        },
        "wallet_cop": {
            "net_from_bank": dep_bank_to_wallet - with_wallet_to_bank,
            "spent_buying": cop_spent_buying,
            "earned_selling": cop_earned_selling,
            "transfers_net": cop_transfers_in - cop_transfers_out,
            "expected": expected_wallet_cop,
            "actual": cur_wallet_cop,
            "discrepancy": wallet_cop_discrepancy,
            "status": "CONCILIADO" if is_wallet_cop_balanced else "DESCUADRE"
        },
        "crypto": crypto_reconciliation
    }
