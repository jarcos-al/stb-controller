"""
Explorador de KeyValues G-MScreen
==================================
Se conecta DIRECTAMENTE al decodificador (sin proxy/sniffer) y envía
cada KeyValue uno a uno. Tú miras la tele y dices qué hace cada código.

No necesita iPhone ni sniffer. Solo conexión directa al deco.

Uso:
    python explore_keys.py [--host 192.168.50.37] [--start 0] [--end 100]
"""

import socket
import struct
import zlib
import json
import time
import sys
import argparse
from pathlib import Path

DECO_HOST = "192.168.50.37"
DECO_PORT = 20000
OUTPUT_FILE = Path("gmscreen_keymap_explored.json")

XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"

# Teclas ya confirmadas (sincronizado con GMSCREEN_KEYS en gmscreen.py)
KNOWN_KEYS = {
    "1":  "UP",
    "2":  "DOWN",
    "3":  "LEFT",
    "4":  "RIGHT",
    "5":  "OK",
    "6":  "MENU",
    "7":  "EXIT",
    "8":  "RED",
    "9":  "GREEN",
    "10": "YELLOW",
    "11": "BLUE",
    "12": "0",
    "13": "1",
    "14": "2",
    "15": "3",
    "16": "4",
    "17": "5",
    "18": "6",
    "19": "7",
    "20": "8",
    "21": "9",
    "23": "MUTE",
    "26": "TIMER",
    "29": "BACK",
    "30": "SAT",
    "31": "SUBTITLE",
    "32": "EPG",
    "34": "TEXT",
    "35": "VOL_UP",
    "36": "VOL_DOWN",
    "37": "CH_UP",
    "38": "CH_DOWN",
    "42": "POWER",
    "58": "REC",
    "61": "PLAY",
    "62": "STOP",
    "63": "PAUSE",
}

# KeyValues probados que no hicieron nada (para saltar)
DEAD_KEYS = {
    0,
    24, 25, 27, 28, 33,
    39, 40, 41, 43, 44, 45,
    46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,
    59, 60,
    64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75,
    76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87,
    88, 89, 90, 91,
}

# Botones que aún faltan por descubrir
PENDING_BUTTONS = [
    "INFO", "FF", "REW",
    "FAV", "AUDIO", "RECALL", "TV_RADIO",
]


def build_packet(xml_body: str) -> bytes:
    """Construye un paquete ALi Start/End."""
    full_xml = f"{XML_HEADER}{xml_body}"
    length_str = str(len(full_xml)).zfill(7)
    return f"Start{length_str}End{full_xml}".encode("utf-8")


def read_response(sock: socket.socket, timeout: float = 3.0) -> str:
    """Lee una respuesta del deco. Puede ser GCDH o RAW."""
    sock.settimeout(timeout)
    try:
        data = sock.recv(4096)
        if not data:
            return "[sin respuesta]"

        # Intentar parsear GCDH
        if data[:4] == b'GCDH' and len(data) >= 16:
            payload_len = struct.unpack_from('<I', data, 4)[0]
            payload = data[16:16 + payload_len]

            # Si falta payload, leer más
            while len(payload) < payload_len:
                more = sock.recv(4096)
                if not more:
                    break
                payload += more
                payload = payload[:payload_len]

            # Descomprimir zlib si aplica
            if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
                try:
                    payload = zlib.decompress(payload)
                except Exception:
                    pass

            return payload.decode("utf-8", errors="replace").strip()
        else:
            return f"[RAW {len(data)}B]"
    except socket.timeout:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"


def do_handshake(sock: socket.socket) -> bool:
    """Hace el handshake inicial con el deco (req=998, 32, 19)."""
    # req=998: Device identification (inventamos un UUID)
    device_xml = (
        '<Command request="998"><parm>'
        '<DeviceName>ExploreKeys</DeviceName>'
        '<DeviceModel>Python</DeviceModel>'
        '<UUID>explore-keys-0000-0000-000000000000</UUID>'
        '</parm></Command>'
    )
    sock.sendall(build_packet(device_xml))
    resp = read_response(sock, timeout=5.0)
    print(f"  Handshake 998: {resp[:60]}")

    # req=32: Appstore URL
    sock.sendall(build_packet('<Command request="32" />'))
    resp = read_response(sock, timeout=5.0)
    print(f"  Handshake  32: {resp[:80]}")

    # req=19: Initial status
    sock.sendall(build_packet('<Command request="19" />'))
    resp = read_response(sock, timeout=5.0)
    print(f"  Handshake  19: {resp[:80]}")

    return True


def send_ping(sock: socket.socket) -> bool:
    """Envía ping (req=26) para mantener la conexión viva."""
    try:
        sock.sendall(build_packet('<Command request="26" />'))
        read_response(sock, timeout=2.0)
        return True
    except Exception:
        return False


def send_key(sock: socket.socket, key_value: int) -> str:
    """Envía un KeyValue y devuelve la respuesta."""
    drain_socket(sock)  # limpiar buffer antes de enviar
    xml = f'<Command request="1040"><parm><KeyValue>{key_value}</KeyValue></parm></Command>'
    sock.sendall(build_packet(xml))
    resp = read_response(sock, timeout=2.0)
    time.sleep(0.5)  # dar tiempo al deco para procesar completamente
    return resp


def drain_socket(sock: socket.socket):
    """Drena cualquier dato pendiente en el socket."""
    sock.setblocking(False)
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
    except BlockingIOError:
        pass
    finally:
        sock.setblocking(True)


def ask_button(kv: int, pending: set) -> str | None:
    """Muestra menú de botones pendientes y devuelve la selección."""
    sorted_pending = sorted(pending)

    print(f"\n        \033[93mBotones pendientes ({len(sorted_pending)}):\033[0m")
    cols = 4
    for i, btn in enumerate(sorted_pending):
        end = "\n" if (i + 1) % cols == 0 else ""
        print(f"          \033[36m{i+1:2d}\033[0m) {btn:<12}", end=end)
    if len(sorted_pending) % cols != 0:
        print()

    print(f"\n         \033[90m 0) Nada/Skip   r) Reenviar   x) Reconectar   q) Fin\033[0m")
    raw = input(f"        → Elige número, nombre, o comando: ").strip()

    if not raw or raw == "0":
        return None
    if raw.lower() == "q":
        return "__FIN__"
    if raw.lower() == "x":
        return "__RECONECTAR__"
    if raw.lower() == "r":
        return "__REENVIAR__"

    # Si es un número, buscar en la lista
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(sorted_pending):
            return sorted_pending[idx]
    except ValueError:
        pass

    # Si escribió un nombre libre, aceptarlo
    return raw.upper()


def connect_to_deco(host: str, port: int) -> socket.socket:
    """Conecta al deco y hace handshake."""
    print(f"\n  Conectando a {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.settimeout(None)
    print(f"  ✓ Conectado\n")

    print("  Handshake:")
    do_handshake(sock)
    print()
    return sock


def main():
    parser = argparse.ArgumentParser(description="Explorador de KeyValues G-MScreen")
    parser.add_argument("--host", default=DECO_HOST, help=f"IP del deco (default {DECO_HOST})")
    parser.add_argument("--port", type=int, default=DECO_PORT, help="Puerto (default 20000)")
    parser.add_argument("--start", type=int, default=0, help="KeyValue inicial (default 0)")
    parser.add_argument("--end", type=int, default=100, help="KeyValue final (default 100)")
    parser.add_argument("--skip-known", action="store_true", help="Saltar teclas ya conocidas")
    parser.add_argument("--auto", action="store_true",
                        help="Modo automático: envía cada tecla con pausa, sin pedir input")
    args = parser.parse_args()

    print("\033[1m")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   G-MScreen — Explorador de KeyValues               ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\033[0m")
    print(f"  Deco: {args.host}:{args.port}")
    print(f"  Rango: KeyValue {args.start} → {args.end}")

    if args.skip_known:
        print(f"  Saltando {len(KNOWN_KEYS)} teclas ya conocidas")

    # Cargar resultados anteriores
    prev_results: dict[str, str] = {}
    if OUTPUT_FILE.exists():
        try:
            prev_data = json.loads(OUTPUT_FILE.read_text())
            prev_results = prev_data.get("new_keys", {})
            print(f"  Cargados {len(prev_results)} resultados anteriores de {OUTPUT_FILE.name}")
        except Exception:
            pass

    sock = connect_to_deco(args.host, args.port)

    results: dict[str, str] = dict(prev_results)  # empezar con los anteriores
    pending = set(PENDING_BUTTONS)  # botones que faltan
    # Quitar del menú los ya descubiertos (anteriores + conocidos)
    for name in results.values():
        pending.discard(name)
    for name in KNOWN_KEYS.values():
        pending.discard(name)
    ping_counter = 0

    try:
        for kv in range(args.start, args.end + 1):
            kv_str = str(kv)

            if args.skip_known and kv_str in KNOWN_KEYS:
                print(f"  [{kv:3d}] \033[90m{KNOWN_KEYS[kv_str]} (ya conocida, saltada)\033[0m")
                continue

            # Saltar KeyValues ya explorados en sesiones anteriores
            if kv_str in prev_results:
                label = prev_results[kv_str]
                print(f"  [{kv:3d}] \033[90m{label} (ya explorado, saltado)\033[0m")
                continue

            # Saltar KeyValues que no hicieron nada
            if kv in DEAD_KEYS:
                print(f"  [{kv:3d}] \033[90m(nada, saltado)\033[0m")
                continue

            known_label = f" (conocida: {KNOWN_KEYS[kv_str]})" if kv_str in KNOWN_KEYS else ""

            # Enviar ping cada 5 teclas para mantener la conexión
            ping_counter += 1
            if ping_counter % 5 == 0:
                if not send_ping(sock):
                    print("  ⚠ Ping fallido, reconectando...")
                    sock.close()
                    sock = connect_to_deco(args.host, args.port)

            # Enviar la tecla
            resp = send_key(sock, kv)

            if args.auto:
                print(f"  [{kv:3d}] Enviado{known_label} — resp: {resp[:50]}")
                time.sleep(1.5)
            else:
                print(f"\n  \033[1m[{kv:3d}] KeyValue={kv} enviado al deco{known_label}\033[0m")
                print(f"        Respuesta: {resp[:60]}")
                answer = ask_button(kv, pending)

                if answer == "__FIN__":
                    break
                elif answer == "__RECONECTAR__":
                    sock.close()
                    sock = connect_to_deco(args.host, args.port)
                    resp = send_key(sock, kv)
                    print(f"        Re-enviado. Respuesta: {resp[:60]}")
                    answer = ask_button(kv, pending)
                    if answer and not answer.startswith("__"):
                        results[kv_str] = answer
                        pending.discard(answer)
                        print(f"        ✓ \033[92m{answer} = KeyValue {kv}\033[0m")
                elif answer == "__REENVIAR__":
                    resp = send_key(sock, kv)
                    print(f"        Re-enviado. Respuesta: {resp[:60]}")
                    answer = ask_button(kv, pending)
                    if answer and not answer.startswith("__"):
                        results[kv_str] = answer
                        pending.discard(answer)
                        print(f"        ✓ \033[92m{answer} = KeyValue {kv}\033[0m")
                elif answer is None:
                    pass  # skip / nada
                else:
                    results[kv_str] = answer
                    pending.discard(answer)
                    print(f"        ✓ \033[92m{answer} = KeyValue {kv}\033[0m")

    except KeyboardInterrupt:
        print("\n")
    finally:
        sock.close()

    # ── Resumen ──
    # Combinar con las ya conocidas
    all_keys = dict(KNOWN_KEYS)
    all_keys.update({v: k for k, v in results.items()})  # nombre → código
    code_to_name = dict(KNOWN_KEYS)
    code_to_name.update(results)

    if results:
        print("\033[1m")
        print("═══════════════════════════════════════════════════════")
        print("  NUEVAS TECLAS DESCUBIERTAS")
        print("═══════════════════════════════════════════════════════")
        print("\033[0m")

        for code, name in sorted(results.items(), key=lambda x: int(x[0])):
            print(f"  KeyValue {code:>3} = {name}")

        # Fragmento para gmscreen.py
        print("\n\033[1m  Fragmento para gmscreen.py:\033[0m")
        print("  ─────────────────────────────")
        for code, name in sorted(results.items(), key=lambda x: int(x[0])):
            print(f'    "{name}": "{code}",')

    # Guardar JSON
    output = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "new_keys": results,
        "all_known": code_to_name,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n  \033[96mGuardado en: {OUTPUT_FILE.resolve()}\033[0m\n")


if __name__ == "__main__":
    main()
