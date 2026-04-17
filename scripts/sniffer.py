"""
G-MScreen MITM Proxy / Sniffer para Qviart Dual
================================================
Intercepta el tráfico entre la app G-MScreen (iPhone) y el decodificador.
- Parsea el protocolo Start/End + XML de ALi automáticamente.
- Extrae y muestra KeyValue codes con nombre de tecla si ya está mapeado.
- Descomprime respuestas GCDH (incluyendo zlib).
- Guarda un log JSON con el diccionario de teclas descubiertas.

Uso:
    python sniffer.py [--host 192.168.50.37] [--port 20000] [--listen 20000]
"""

import socket
import threading
import sys
import zlib
import re
import json
import struct
import argparse
from datetime import datetime
from pathlib import Path

# ── Configuración por defecto ──────────────────────────────────────────────────
DEFAULT_LOCAL_PORT  = 20000
DEFAULT_REMOTE_HOST = "192.168.50.37"
DEFAULT_REMOTE_PORT = 20000
LOG_FILE            = Path("gmscreen_keymap.json")
EVENT_LOG           = Path("/tmp/gmscreen_events.log")  # Log simple para capture_keys.py

# ── Mapa de teclas ya conocidas (se actualizará en tiempo real) ────────────────
KNOWN_KEYS: dict[str, str] = {
    "1":  "OK",
    "2":  "DOWN",
    "3":  "UP",
    "4":  "LEFT",
    "5":  "RIGHT",
    "6":  "BACK",
    "7":  "POWER",
    "8":  "REW",
    "9":  "FF",
    "10": "MENU",
    "11": "EXIT",
    "23": "REC",
    "42": "VOL_UP",
    "82": "STOP",
}

# Mapa inverso nombre → código (para mostrar en el resumen final)
_key_by_name: dict[str, str] = {v: k for k, v in KNOWN_KEYS.items()}

# Registro de sesión: {key_value: {"name": "?", "count": N}}
_session_keys: dict[str, dict] = {}
_session_lock = threading.Lock()

# ── Protocolo ALi ──────────────────────────────────────────────────────────────
_RE_START_END = re.compile(
    rb'Start(\d{7})End(.*)',
    re.DOTALL,
)
_RE_REQUEST   = re.compile(rb'request="(\d+)"')
_RE_KEY_VALUE = re.compile(rb'<KeyValue>(\d+)</KeyValue>')

def _parse_ali_packet(data: bytes) -> list[dict]:
    """
    Extrae todos los paquetes ALi que vengan en un chunk TCP.
    Retorna lista de dicts con keys: raw_xml, request_id, key_value.
    """
    results = []
    remaining = data
    while True:
        m = _RE_START_END.search(remaining)
        if not m:
            break
        declared_len = int(m.group(1))
        xml_bytes    = m.group(2)[:declared_len]
        req_m        = _RE_REQUEST.search(xml_bytes)
        kv_m         = _RE_KEY_VALUE.search(xml_bytes)
        results.append({
            "raw_xml":    xml_bytes.decode("utf-8", errors="replace").strip(),
            "request_id": req_m.group(1).decode() if req_m else None,
            "key_value":  kv_m.group(1).decode() if kv_m else None,
        })
        # Avanzar en el buffer por si hay más paquetes concatenados
        remaining = remaining[m.start() + 5 + 7 + 3 + declared_len:]
        if not remaining:
            break
    return results

_RE_GCDH = re.compile(rb'GCDH')

def _parse_gcdh_response(data: bytes) -> list[dict]:
    """
    Extrae respuestas GCDH del decodificador.
    Header: 16 bytes — 'GCDH' + payload_len (uint32 LE) + 8 bytes extra
    """
    results = []
    offset = 0
    while offset < len(data):
        idx = data.find(b'GCDH', offset)
        if idx == -1:
            break
        header = data[idx: idx + 16]
        if len(header) < 16:
            break
        payload_len = struct.unpack_from('<I', header, 4)[0]
        payload = data[idx + 16: idx + 16 + payload_len]
        text = ""
        compressed = False
        if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
            try:
                payload = zlib.decompress(payload)
                compressed = True
            except Exception:
                pass
        text = payload.decode("utf-8", errors="replace").strip()
        results.append({
            "compressed":   compressed,
            "payload_len":  payload_len,
            "text":         text,
        })
        offset = idx + 16 + payload_len
    return results

# ── Helpers de presentación ────────────────────────────────────────────────────
COLORS = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "cyan":   "\033[96m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "blue":   "\033[94m",
    "grey":   "\033[90m",
}

def _c(color: str, text: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"

def hexdump(src: bytes, prefix: str = "") -> str:
    length = 16
    lines = []
    for i in range(0, len(src), length):
        chunk = src[i: i + length]
        hexa  = " ".join(f"{b:02X}" for b in chunk)
        text  = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
        lines.append(f"{_c('grey', f'{prefix}{i:04X}   {hexa:<{length*3}}   {text}')}")
    return "\n".join(lines)

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def _log(msg: str, **kwargs):
    """Print con flush forzado."""
    print(msg, flush=True, **kwargs)

def _record_key(key_value: str, name: str = "?"):
    """Registra una tecla en el diccionario de sesión y escribe al event log."""
    with _session_lock:
        if key_value not in _session_keys:
            _session_keys[key_value] = {"name": name, "count": 0}
        _session_keys[key_value]["count"] += 1
        if _session_keys[key_value]["name"] == "?" and name != "?":
            _session_keys[key_value]["name"] = name
    # Escribir evento al log simple (sin ANSI) para capture_keys.py
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(EVENT_LOG, "a") as f:
        f.write(f"{ts} KeyValue={key_value} name={name}\n")
        f.flush()

def _save_keymap():
    """Escribe el diccionario descubierto en gmscreen_keymap.json."""
    with _session_lock:
        data = {
            "captured_at": datetime.now().isoformat(),
            "keys": {kv: info for kv, info in sorted(_session_keys.items(), key=lambda x: int(x[0]))},
        }
    LOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ── Hilo de reenvío ────────────────────────────────────────────────────────────
def forward(source: socket.socket, destination: socket.socket, direction: str):
    is_client = "→ Deco" in direction   # iPhone → Deco
    buf = b""
    MAX_BUF = 65536  # Evitar acumulación infinita

    while True:
        try:
            chunk = source.recv(4096)
            if not chunk:
                _log(_c("yellow", f"[·] Conexión cerrada: {direction}"))
                break

            # ── PRIMERO reenviar, LUEGO parsear ──
            # Así el proxy nunca bloquea el tráfico aunque falle el logging
            try:
                destination.sendall(chunk)
            except Exception as e:
                _log(_c("red", f"[!] Error reenviando {direction}: {e}"))
                break

            # ── Ahora intentar parsear para logging ──
            buf += chunk

            try:
                if is_client:
                    _process_client_data(buf, direction)
                else:
                    _process_server_data(buf, direction)
            except Exception as e:
                _log(_c("red", f"[!] Error parseando {direction}: {e}"))

            # Limpiar buf después de procesar (o si es demasiado grande)
            # Buscar el último byte consumido
            buf = b""
            if len(buf) > MAX_BUF:
                buf = b""

        except Exception as e:
            _log(_c("red", f"[!] Error {direction}: {e}"))
            break

    # Limpiar sockets al terminar el hilo
    _log(_c("grey", f"[·] Hilo {direction} terminado."))
    try:
        source.close()
    except Exception:
        pass
    try:
        destination.close()
    except Exception:
        pass


def _process_client_data(data: bytes, direction: str):
    """Parsea y loggea datos del cliente (iPhone → Deco)."""
    packets = _parse_ali_packet(data)
    if packets:
        for pkt in packets:
            req = pkt["request_id"]
            kv  = pkt["key_value"]

            if kv is not None:
                name = KNOWN_KEYS.get(kv, "?")
                _record_key(kv, name)
                _save_keymap()

                label = _c("bold", f"KeyValue={kv}")
                if name != "?":
                    label += f"  →  {_c('green', name)}"
                else:
                    label += f"  →  {_c('yellow', 'DESCONOCIDA — anotada en ' + str(LOG_FILE))}"

                _log(
                    f"\n{_c('cyan', _ts())}  {_c('bold', direction)}\n"
                    f"  🎮  {label}\n"
                    f"  XML: {_c('grey', pkt['raw_xml'])}"
                )
            elif req == "26":
                _log(f"{_c('grey', _ts())}  {direction}  {_c('grey', '[PING/Status req=26]')}")
            elif req == "998":
                _log(f"{_c('grey', _ts())}  {direction}  {_c('grey', '[HANDSHAKE device-id req=998]')}")
            elif req == "32":
                _log(f"{_c('grey', _ts())}  {direction}  {_c('grey', '[HANDSHAKE appstore-url req=32]')}")
            elif req == "19":
                _log(f"{_c('grey', _ts())}  {direction}  {_c('grey', '[HANDSHAKE status req=19]')}")
            else:
                _log(
                    f"\n{_c('cyan', _ts())}  {direction}\n"
                    f"  CMD req={req}  XML: {_c('grey', pkt['raw_xml'])}"
                )
    else:
        _log(f"{_c('grey', _ts())}  {direction}  {_c('grey', f'[RAW {len(data)}B]')}")


def _process_server_data(data: bytes, direction: str):
    """Parsea y loggea datos del servidor (Deco → iPhone)."""
    responses = _parse_gcdh_response(data)
    if responses:
        for resp in responses:
            zlabel = _c("blue", "[zlib]") if resp["compressed"] else ""
            snippet = resp["text"][:120].replace("\n", " ")
            _log(
                f"{_c('grey', _ts())}  {direction}  "
                f"GCDH {zlabel} {resp['payload_len']}B  "
                f"{_c('grey', snippet)}"
            )
    else:
        _log(f"{_c('grey', _ts())}  {direction}  {_c('grey', f'[RAW {len(data)}B]')}")

# ── Servidor proxy ─────────────────────────────────────────────────────────────
def start_proxy(local_port: int, remote_host: str, remote_port: int):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", local_port))
    server.listen(5)

    # Limpiar event log al iniciar
    EVENT_LOG.write_text("")

    _log(_c("bold", "\n╔══════════════════════════════════════════════════╗"))
    _log(_c("bold",   "║   G-MScreen MITM Sniffer — Qviart Dual          ║"))
    _log(_c("bold",   "╚══════════════════════════════════════════════════╝"))
    _log(f"  Escuchando en    : {_c('cyan', f'0.0.0.0:{local_port}')}")
    _log(f"  Reenviando a     : {_c('cyan', f'{remote_host}:{remote_port}')}")
    _log(f"  Log de teclas    : {_c('cyan', str(LOG_FILE.resolve()))}")
    _log(f"  Event log        : {_c('cyan', str(EVENT_LOG.resolve()))}")
    _log(f"  Teclas conocidas : {_c('green', str(len(KNOWN_KEYS)))}")
    _log("")
    _log(_c("yellow", "  ► En el iPhone, configura la IP de ESTE equipo como destino."))
    _log(_c("yellow", "  ► Pulsa cada botón de la app G-MScreen original."))
    _log(_c("yellow", "  ► Al terminar, Ctrl+C para ver el resumen.\n"))

    while True:
        _log(_c("grey", "[·] Esperando conexión del iPhone..."))
        client_socket, addr = server.accept()
        _log(_c("green", f"\n[+] Conexión desde {addr}"))

        target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_socket.settimeout(30)
        try:
            target_socket.connect((remote_host, remote_port))
        except Exception as e:
            _log(_c("red", f"[-] No se pudo conectar al Qviart: {e}"))
            client_socket.close()
            continue

        target_socket.settimeout(None)
        _log(_c("green", "[+] Túnel establecido. Interceptando tráfico...\n"))

        t1 = threading.Thread(
            target=forward,
            args=(client_socket, target_socket, "iPhone → Deco"),
            daemon=True,
        )
        t2 = threading.Thread(
            target=forward,
            args=(target_socket, client_socket, "Deco → iPhone"),
            daemon=True,
        )
        t1.start()
        t2.start()

        # Esperar a que ambos hilos terminen antes de aceptar nueva conexión
        t1.join()
        t2.join()
        _log(_c("yellow", "\n[·] Conexión terminada. Reconecta el iPhone para seguir capturando.\n"))

def _print_summary():
    """Muestra el diccionario de teclas capturadas en esta sesión."""
    with _session_lock:
        keys = dict(_session_keys)

    if not keys:
        print("\n[!] No se capturó ninguna tecla en esta sesión.")
        return

    print(_c("bold", "\n\n═══ RESUMEN DE TECLAS CAPTURADAS ════════════════════════"))
    print(f"{'KeyValue':<12} {'Nombre':<20} {'Pulsaciones'}")
    print("─" * 46)
    for kv, info in sorted(keys.items(), key=lambda x: int(x[0])):
        name  = _c("green", info["name"]) if info["name"] != "?" else _c("yellow", "DESCONOCIDA")
        count = info["count"]
        print(f"  {kv:<10} {name:<30} {count}")

    print(f"\n  Guardado en: {_c('cyan', str(LOG_FILE.resolve()))}")
    print()

    # Generar fragmento listo para pegar en gmscreen.py
    print(_c("bold", "═══ FRAGMENTO PARA gmscreen.py ══════════════════════════"))
    print("GMSCREEN_KEYS = {")
    for kv, info in sorted(keys.items(), key=lambda x: int(x[0])):
        if info["name"] != "?":
            print(f'    "{info["name"]}": "{kv}",')
        else:
            print(f'    # "NOMBRE_{kv}": "{kv}",   ← pendiente de identificar')
    print("}")

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="G-MScreen MITM Sniffer para Qviart Dual")
    parser.add_argument("--host",   default=DEFAULT_REMOTE_HOST, help="IP del decodificador")
    parser.add_argument("--port",   type=int, default=DEFAULT_REMOTE_PORT, help="Puerto del deco (default 20000)")
    parser.add_argument("--listen", type=int, default=DEFAULT_LOCAL_PORT,  help="Puerto local de escucha (default 20000)")
    args = parser.parse_args()

    try:
        start_proxy(args.listen, args.host, args.port)
    except KeyboardInterrupt:
        _print_summary()
        sys.exit(0)
