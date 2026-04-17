# Guía de desarrollo

## Requisitos

- Python 3.12+
- Node.js 18+
- Un decodificador satélite compatible con G-MScreen en la red local

## Setup del entorno

```bash
# Clonar
git clone https://github.com/tu-usuario/gmscreen.git
cd gmscreen

# Python
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Node
cd frontend && npm install && cd ..

# Configuración
cp .env.example .env
# Editar config/stb-control.yaml con la IP de tu decodificador
```

## Ejecutar en desarrollo

Se necesitan **dos terminales**:

### Terminal 1 — Backend

```bash
source .venv/bin/activate
DATA_DIR=./data CONFIG_DIR=./config \
  uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

- **Frontend:** http://localhost:5173 (proxy automático a :8080)
- **Backend API:** http://localhost:8080/api/
- **WebSocket:** ws://localhost:8080/ws

### En un solo terminal (producción local)

```bash
# Build del frontend
cd frontend && npm run build && cd ..

# Servir todo desde el backend
DATA_DIR=./data CONFIG_DIR=./config \
  uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

## Estructura del backend

### Patrón adaptador

El backend usa el patrón **Adapter** para abstraer la comunicación con distintos tipos de decodificadores:

```
STBAdapter (base abstracta)
├── GMScreenAdapter  → Protocolo ALi/G-MScreen (TCP :20000)
├── Enigma2Adapter   → API web Enigma2 (placeholder)
└── MockAdapter      → Simulador para desarrollo
```

Para añadir soporte para un nuevo tipo de decodificador:

1. Crear `backend/adapters/nuevo.py` extendiendo `STBAdapter`
2. Registrarlo en `backend/adapters/registry.py`
3. Configurar en `config/stb-control.yaml` con `adapter: "nuevo"`

### Flujo de datos en tiempo real

```
STB ←TCP→ GMScreenAdapter ←poll 5s→ _poll_status()
                                          │
                                    WebSocket Manager
                                          │
                                    ┌─────┴─────┐
                                    │  Cliente 1 │
                                    │  Cliente 2 │
                                    │  ...       │
                                    └────────────┘
```

El backend hace polling del estado cada 5 segundos y lo broadcast a todos los clientes WebSocket conectados.

### Endpoints clave

Ver [README.md](../README.md#api-rest) para la tabla completa de endpoints.

## Estructura del frontend

### Componentes principales

| Componente | Descripción |
|-----------|-------------|
| `App.svelte` | Layout con navegación por pestañas |
| `RemoteControl.svelte` | Mando a distancia virtual |
| `ChannelList.svelte` | Lista de canales con búsqueda y filtro por bouquet |
| `StatusPanel.svelte` | Estado del STB (canal, señal, programa) |
| `EpgView.svelte` | Guía electrónica de programas |
| `ConnectionSettings.svelte` | Gestión de conexión (scan + manual) |

### Stores (estado reactivo)

| Store | Contenido |
|-------|-----------|
| `websocket.js` | Conexión WS, estado del STB en tiempo real |
| `app.js` | Estado de la UI (toasts, navegación) |

### API client

`utils/api.js` — Wrapper sobre `fetch` con todos los métodos de la API REST.

## Scripts de ingeniería inversa

En `scripts/` se encuentran las herramientas usadas para descifrar el protocolo:

| Script | Propósito |
|--------|-----------|
| `sniffer.py` | Proxy MITM entre la app móvil y el STB |
| `capture_keys.py` | Captura interactiva de teclas vía sniffer |
| `explore_keys.py` | Exploración exhaustiva de códigos de tecla |
| `explore_requests.py` | Exploración de IDs de request |
| `fetch_channels.py` | Descarga completa de canales del STB |
| `retest_keys.py` | Re-test contextual de teclas "muertas" |
| `test_zap.py` | Test de cambio de canal |

Estos scripts son independientes del backend y se conectan directamente al STB.

## Docker

### Build

```bash
docker compose build
```

### Deploy

```bash
docker compose up -d
```

El Dockerfile usa un build multi-stage:
1. **Stage 1 (Node):** Compila el frontend Svelte
2. **Stage 2 (Python):** Sirve el frontend compilado + API

El servicio usa `network_mode: host` para acceso directo a la red local del decodificador.

## Troubleshooting

### "No se puede conectar al decodificador"

1. Verifica que el deco está encendido y en la misma red
2. Comprueba la IP: `ping 192.168.x.x`
3. Comprueba el puerto: `nc -zv 192.168.x.x 20000`
4. **Cierra la app G-MScreen del móvil** — el STB solo permite una conexión simultánea

### "La conexión se cae frecuentemente"

El STB cierra conexiones inactivas tras ~30s. El backend envía keepalive automáticos, pero si la conexión se pierde, usa el botón de reconexión en la interfaz.

### "El scan de red no encuentra el decodificador"

- El deco puede estar apagado o en standby profundo
- Si ya estás conectado, tu propio deco aparecerá igualmente (se obtiene de la conexión activa)
- Otros dispositivos en la red con puerto 20000 abierto también aparecerán
