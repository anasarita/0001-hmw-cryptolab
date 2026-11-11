# 🛡️ Crypto Lab — Simulador Financiero & Auditoría Forense

Plataforma interactiva para talleres académicos y profesionales de **auditoría forense digital y finanzas cripto**. Permite simular un mercado financiero en tiempo real (Market Replay con datos de Binance/CoinGecko), habilitar trading multi-usuario simultáneo desde teléfonos móviles vía QR en red local, y ejecutar auditorías forenses automáticas con detección de tipologías de fraude (wash trading, estructuración/pitufeo, balance patching, etc.).

---

## ✨ Características Principales

- **📈 Motor de Market Replay Histórico Real (D-015)**: Recrea velas y movimientos de precios reales de Bitcoin (BTC), Ethereum (ETH) y Tether (USDT) acelerados para sesiones de 30-45 minutos.
- **📱 Conexión QR Multi-usuario (hasta 30 participantes)**: Los estudiantes o participantes acceden desde sus celulares escaneando un código QR en pantalla sin necesidad de instalar apps.
- **💼 Billetera & Exchange Simulado**: Transacciones de depósito, retiro, compra, venta y transferencias peer-to-peer (P2P) con hashing criptográfico SHA-256 e inmutabilidad contable.
- **🔍 Módulo de Auditoría Forense Digital**:
  - Detección automática de tipologías sospechosas (Wash Trading, Estructuración/Smurfing, Fondos de origen ilícito, Inflación ficticia).
  - Trazabilidad y reconstrucción de grafos de transacciones por participante.
  - Generación de informe forense pericial con dictamen y firma digital.
- **📊 Gráficos Financieros Profesionales**: Integración con TradingView Lightweight Charts para análisis técnico en tiempo real.
- **🔒 Seguridad & Configuración Local**: Autenticación administrativa con PBKDF2/SHA-256, variables de entorno aisladas (`.env`).

---

## 🚀 Requisitos e Instalación

### Requisitos Previos
- **Python 3.10+** instalado y agregado al PATH del sistema.
- Conexión a la misma red Wi-Fi (para que los teléfonos móviles se conecten a la IP local).

### Instalación Rápida

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/anasarita/0001-hmw-cryptolab.git
   cd 0001-hmw-cryptolab
   ```

2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configurar variables de entorno:
   ```bash
   cp .env.example .env
   # Edita el archivo .env con tus credenciales seguras
   ```

---

## ⚡ Inicio del Sistema

### En Windows (1 Clic)
Haz doble clic en:
```text
INICIAR_CRYPTO_LAB.bat
```

### O por Terminal
```bash
python iniciar_cryptolab.py
```

- **Panel de Administración (Docente/Proyector)**: `http://localhost:8000/admin`
- **Portal de Participantes (Estudiantes)**: `http://<TU_IP_LOCAL>:8000`

Para una guía detallada paso a paso, consulta el [MANUAL_DE_USO.md](MANUAL_DE_USO.md).

---

## 🧪 Pruebas Automatizadas

El proyecto incluye suites de pruebas unitarias y de integración para validar la lógica forense, el motor de replay y las APIs:

```bash
python test_market_replay.py
python test_api_endpoints.py
python test_case_horizonte.py
python test_complete_audit_report.py
```

---

## 📁 Estructura del Proyecto

```text
├── server.py                       # Servidor API FastAPI & WebSockets/SSE
├── database.py                     # Capa de datos SQLite, modelos y hashes
├── forensics.py                    # Motor de análisis pericial y reglas forenses
├── replay_engine.py                # Motor de simulación y reproducción de mercado
├── prices.py                       # Oráculo de precios y cotizaciones
├── prepare_historical_dataset.py   # Procesador de series de tiempo financieras
├── descargar_datos_historicos.py   # Utilidad para capturar datos de CoinGecko
├── iniciar_cryptolab.py            # Script orquestador de arranque
├── INICIAR_CRYPTO_LAB.bat          # Lanzador directo de Windows
├── requirements.txt                # Dependencias de Python
├── MANUAL_DE_USO.md                # Guía completa de uso en aula
├── static/                         # Frontend (HTML5, Vanilla CSS, JS moderno)
│   ├── index.html                  # Portal de participante / billetera móvil
│   ├── app.js                      # Lógica cliente para celular
│   ├── admin.html                  # Panel de control del docente / auditor
│   ├── admin.js                    # Tableros y visualización de auditoría
│   └── styles.css                  # Sistema de diseño responsive
└── tests/                          # Scripts de validación y casos de prueba
```

---

## 📜 Licencia & Propósito

Desarrollado para fines educativos y académicos en auditoría forense, análisis de fraudes en finanzas descentralizadas y formación en ciberseguridad financiera.
