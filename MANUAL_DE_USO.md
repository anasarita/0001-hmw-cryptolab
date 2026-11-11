# 🛡️ CRYPTO LAB — MANUAL DE USO Y GUÍA DE PRESENTACIÓN

**¡Bienvenida/o! Tu aplicación está completamente construida, probada y lista para tu presentación.**

Este manual está redactado en español sencillo, paso a paso, para que puedas ejecutar la simulación académica mañana sin necesidad de saber programar.

---

## ⚡ 1. CÓMO INICIAR LA APLICACIÓN (EN 1 SOLO CLIC)

1. En tu computador, abre la carpeta del proyecto: `Auditoria Forense` (en tu Escritorio).
2. Busca el archivo llamado:
   👉 **`INICIAR_CRYPTO_LAB.bat`**
3. **Haz doble clic sobre él.**
4. Se abrirá una ventana de fondo negro (consola del servidor) que dirá:
   ```text
   ========================================================================
         CRYPTO LAB - SIMULADOR FINANCIERO & AUDITORIA FORENSE
   ========================================================================
    -> Enlace en esta computadora: http://localhost:8000/admin
    -> Enlace para Celulares (misma Wi-Fi): http://[TU_IP_LOCAL]:8000
    -> Usuario Administrador: admin_forense
    -> Contraseña:           [Configurada de forma privada en tu archivo .env local]
   ========================================================================
   ```
5. **Automáticamente se abrirá tu navegador (Chrome o Edge)** en la pantalla del Administrador.
6. **¡Listo! El sistema ya está funcionando.** *(Mantén esa ventana negra abierta durante toda tu clase).*

---

## 📱 2. CÓMO CONECTAR LOS CELULARES DE LOS ASISTENTES (HASTA 30 PERSONAS)

1. Asegúrate de que los celulares y tu computador estén conectados a la **misma red Wi-Fi** (la del aula, oficina o el punto de acceso móvil de tu celular).
2. En tu pantalla de Administrador, ve a la pestaña **"Gestión de Salas"** o **"Monitor de Sala Activa"**.
3. Haz clic en el botón azul **"📽️ Proyectar QR y Enlace"**.
4. Se abrirá un recuadro grande en pantalla con:
   - El **Código QR** gigante.
   - El código corto de la sala (ejemplo: `LAB101`).
   - El enlace web directo (ejemplo: `http://192.168.1.XX:8000/?room=LAB101`).
5. Pide a los participantes que abran la cámara de su celular y **escaneen el código QR**.
6. Al escanearlo, su celular abrirá la aplicación web de inmediato con la sala preseleccionada.
7. Solo deberán escribir su nombre o empresa (ejemplo: `CARLOS_FINANZAS` o `HORIZONTE`) y pulsar **"Entrar a la Sesión"**.

---

## 🏛️ 3. CÓMO CREAR UNA SALA COMO ADMINISTRADOR

1. Ingresa a `http://localhost:8000/admin`.
2. Escribe:
   - **Usuario:** `admin_forense`
   - **Contraseña:** *(Ingresa la clave privada definida en tu archivo `.env` local)*
3. En la pestaña **"Gestión de Salas"**, haz clic en el botón verde **"+ Crear Nueva Sala"**.
4. Llena los 3 campos:
   - **Código de la sala:** Ejemplo: `SALA1` o `LAB2026`.
   - **Nombre de la sesión:** Ejemplo: `Taller de Auditoría Forense - Caso Horizonte`.
   - **Saldo bancario inicial:** Por defecto viene en `50,000,000 COP` (puedes cambiarlo si deseas).
5. Haz clic en **"Crear Sala"**.

---

## 🎬 4. GUÍA PASO A PASO PARA EJECUTAR EL CASO "COMERCIALIZADORA HORIZONTE"

Este es el libreto exacto que puedes seguir en vivo frente a tu audiencia:

### Acto 1: La Operación de la Empresa (Como Participante)
1. Abre una pestaña normal en tu navegador o ingresa desde tu celular a `http://localhost:8000/?room=SALA1`.
2. Como Alias, escribe: **`HORIZONTE`** y pulsa **"Entrar a la Sesión"**.
3. Muestra a la audiencia tu saldo inicial: **50.000.000 COP** en tu cuenta bancaria ficticia.
4. Ve a la pestaña **"🏦 Banco ⇄ Billetera"**:
   - Traslada **45.000.000 COP** a tu billetera operativa.
5. Ve a la pestaña **"⚡ Comprar / Vender"**:
   - Selecciona **USDT** (Tether USD).
   - Compra **10.000 USDT** (el sistema calculará automáticamente la cotización real y la comisión del 0.2%).
   - Confirma la compra. Muestra cómo se descuentan los COP y se acreditan los 10.000 USDT con su Hash criptográfico de confirmación.
6. Ve a la pestaña **"💸 Transferir"**:
   - Selecciona **Transferencia Interna**.
   - Destino: Escribe el alias de otro participante de la sala (ejemplo: **`USUARIO_B`**).
   - Monto: **10.000 USDT**.
   - Pulsa **"Ejecutar Transferencia"**.

### Acto 2: El Salto Intermedio (Pitufeo / Intermediario)
1. Desde otro celular o ventana de incógnito, ingresa como **`USUARIO_B`**.
2. Muestra que tiene los **10.000 USDT** recibidos de `HORIZONTE`.
3. Desde la cuenta de `USUARIO_B`, transfiere esos **10.000 USDT** a **`USUARIO_C`**.

### Acto 3: La Salida Fuera del Perímetro (Dirección Externa)
1. Ingresa como **`USUARIO_C`**.
2. Ve a **"💸 Transferir"** y selecciona **"🌐 Externa (Billetera simulada)"**.
3. Pulsa el botón **"🎲 Generar Dirección de Prueba"** (o pega una dirección tipo `0x98A7F4c1D83e1E7938...`).
4. Transfiere los **10.000 USDT**.
5. Muestra a la audiencia la advertencia: *"Los fondos abandonaron el perímetro interno de Crypto Lab. La trazabilidad interna termina aquí."*

### Acto 4: La Auditoría Forense y el Peritaje (Como Administrador)
1. Regresa a tu panel de Administrador (`http://localhost:8000/admin`).
2. Ve a la pestaña **"🔬 Investigación Forense & Grafo"**.
3. En el menú desplegable, selecciona **`HORIZONTE`**.
4. ¡El sistema desplegará de forma inmediata!:
   - **El Grafo Interactivo:** Las flechas que conectan `HORIZONTE ➔ USUARIO_B ➔ USUARIO_C ➔ Destino Externo (Rojo)`.
   - **Las Alertas de Riesgo Automáticas:**
     - *Conversión Inmediata y Dispersión:* Compró cripto y sacó más del 70% en minutos.
     - *Transferencia a Billetera Externa:* Salida de capital fuera del perímetro de control.
   - **Conciliación Matemática:** Muestra el sello verde de **"✓ CONCILIACIÓN PERFECTA (Discrepancia: 0.00 COP)"**.
5. Haz clic en el botón superior **"📑 Generar Informe de Auditoría"**.
6. Se abrirá el **Informe Pericial Completo** con sus 16 secciones numeradas.
7. Pulsa **"🖨️ Imprimir / Guardar en PDF"** y guárdalo como archivo PDF oficial para proyectarlo o entregarlo.

---

## 📈 5. SISTEMA DE MARKET REPLAY (REQUISITO D-015)

Para tu presentación, el simulador **no depende de conexiones externas lentas ni de caídas de internet**: utiliza el **Motor de Reproducción de Mercado Histórico (Market Replay)**.

### ¿Cómo funciona?
1. **Período Histórico Auténtico (10 de Noviembre de 2026):** Contiene el intervalo real verificado del 10 de noviembre de 2026 en hora legal de Colombia (COT / UTC-5), iniciando exactamente a las **00:00:00 COT (05:00:00 UTC)** hasta el corte real de descarga a las **16:54:30 COT (21:54:30 UTC)**, sumando **16.91 horas efectivas** (204 ticks observados de 5 minutos para BTC, ETH, USDT y SOL). No se agregaron fechas ficticias hacia el futuro.
2. **Velocidad Ajustada a la Clase (33.82x):** Las 16.91 horas efectivas observadas ($60.870\text{ segundos simulados}$) se reproducen de manera fluida y continua en los **30 minutos de tu sesión académica** ($1.800\text{ segundos reales}$), resultando en una velocidad de **$33.82\text{x}$** ($60.870 / 1.800 = 33.82$).
3. **Conversión Documentada USD ➔ COP:** Las cotizaciones internacionales en USD fueron convertidas aplicando la Tasa Representativa del Mercado (TRM) oficial de **$3.269,88 COP/USD** certificada por el Banco de la República de Colombia (https://www.banrep.gov.co/) para el 10 de noviembre de 2026, debidamente auditada en los metadatos.
4. **Distinción Transparente de Cotizaciones:** El sistema distingue en pantalla y en cada recibo contable entre:
   - `● Observado Real`: Precio histórico exacto reportado por la API de mercado en un tick.
   - `▲ Calculado (Interpolado)`: Precio ponderado linealmente segundo a segundo entre observaciones reales.
5. **Sincronización Total desde el Backend:** El servidor es el dueño del reloj central. Todos los participantes conectados desde sus celulares ven exactamente el mismo precio en el mismo segundo. Las órdenes de compra y venta son liquidadas en el backend al precio oficial de ese instante.
6. **Curva Dinámica en Pantalla:** En la pestaña **"Mercado Histórico"**, los participantes ven una gráfica que va avanzando progresivamente minuto a minuto.
7. **Valoración Dinámica del Portafolio:** Conforme los precios varían en el tiempo, el patrimonio de cada participante se actualiza automáticamente.
8. **Controles de la Docente:**
   - En la parte superior de tu panel de Administrador tienes el **Control Maestro de Mercado**:
     - `▶ Reanudar`: Inicia o continúa la marcha del reloj.
     - `⏸ Pausar`: Congela los precios en seco si estás explicando un concepto.
     - `🔄 Reiniciar`: Regresa el mercado al inicio de la jornada (10-Nov 00:00:00 COT).
     - Selector de velocidad: `1x`, `16x`, `33.82x`, `48x` o personalizada.
9. **Descarga de Datos (Opcional):** Si algún día deseas actualizar los datos antes de otra clase, solo debes ejecutar:
   ```powershell
   python descargar_datos_historicos.py
   python prepare_historical_dataset.py
   ```
   Si no hay internet, el sistema mantendrá intacto el conjunto de respaldo del 10 de noviembre de 2026.

---

## 🧹 6. CÓMO LIMPIAR LAS PRUEBAS ANTES DE PRESENTAR MAÑANA

Si hoy practicas y haces transferencias de prueba, puedes dejar la base de datos como nueva ejecutando en la consola de comandos de la carpeta:
```powershell
python reiniciar_base_datos.py
```
Esto borrará las salas y participantes de prueba, dejando la plataforma 100% limpia para mañana con tu usuario y contraseña de administrador listos.

---

## 📊 7. RESUMEN DE COMPONENTES ENTREGADOS

| Requisito | Estado | Observación |
| :--- | :---: | :--- |
| **Market Replay (D-015)** | **TERMINADO (100%)** | Jornada efectiva 10-Nov (00:00 a 16:54 COT, 16.91h) a 33.82x (30 min). Distingue precios reales de calculados. |
| **Servidor y Arquitectura Monolítica** | **TERMINADO (100%)** | FastAPI + SQLite en `0.0.0.0:8000`. Sin dependencias pesadas. |
| **Persistencia e Integridad de Saldos** | **TERMINADO (100%)** | Transacciones atómicas ACID en SQLite con modo WAL y aritmética decimal exacta. |
| **Cuenta Bancaria y Billetera Multiactivo** | **TERMINADO (100%)** | Traslados Banco ⇄ Billetera sin costo, compra/venta con comisión exacta del 0.2%. |
| **Transferencias P2P y Externas** | **TERMINADO (100%)** | Transferencias internas en sala y externas simuladas con hashes criptográficos. |
| **Código QR y LAN Wi-Fi** | **TERMINADO (100%)** | Detección automática de IP local y proyección en alta resolución. |
| **Grafo Forense Visual** | **TERMINADO (100%)** | Vis.js interactivo con respaldo SVG nativo offline. Mapea saltos multietapa y salidas. |
| **Motor de Alertas de Riesgo** | **TERMINADO (100%)** | 5 reglas automáticas: velocidad, conversión rápida, intermediarios, circularidad y fan-in. |
| **Informe Pericial de Auditoría** | **TERMINADO (100%)** | 16 secciones completas con conciliación matemática y exportación a PDF vía navegador. |
| **Pruebas Automatizadas** | **TERMINADO (100%)** | Caso Horizonte y suite de Market Replay verificados con 0.00 discrepancia contable. |

**¡Éxitos en tu presentación de mañana! Tienes una plataforma robusta, elegante y 100% funcional.**
