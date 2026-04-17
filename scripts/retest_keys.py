"""
Re-test de KeyValues "muertos" en contextos específicos.
Envía cada código muerto uno a uno para que el usuario vea si
hace algo en el contexto actual (ej: viendo un canal, en un menú, etc.)
"""

import socket
import struct
import zlib
import json
import time
import sys
from pathlib import Path

DECO_HOST = "192.168.50.37"
DECO_PORT = 20000
OUTPUT_FILE = Path("gmscreen_keymap_explored.json")
XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"

# Códigos que no hicieron nada (quitados: 12=0_NUM, 26=TIMER, 29=BACK, 30=SAT, 45=MUTE)
DEAD_KEYS = sorted([0, 11, 22, 23, 24, 25, 27, 28, 33, 37, 38, 39, 40, 41, 43, 44, 46, 47])

PENDING_BUTTONS = [
    "EXIT", "INFO",
    "CH_UP", "CH_DOWN",
    "PLAY", "PAUSE", "STOP", "FF", "REW", "REC",
    "FAV", "AUDIO", "RECALL", "TV_RADIO",
]


def build_packet(xml_body: str) -> bytes:
    full_xml = f"{XML_HEADER}{xml_body}"
    length_str = str(len(full_xml)).zfill(7)
    return f"Start{length_str}End{full_xml}".encode("utf-8")


def drain_socket(sock):
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


def read_response(sock, timeout=3.0):
    sock.settimeout(timeout)
    try:
        data = sock.recv(4096)
        if not data:
            return ""
        if data[:4] == b'GCDH' and len(data) >= 16:
            payload_len = struct.unpack_from('<I', data, 4)[0]
            payload = data[16:16 + payload_len]
            while len(payload) < payload_len:
                more = sock.recv(4096)
                if not more:
                    break
                payload += more
                payload = payload[:payload_len]
            if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
                try:
                    payload = zlib.decompress(payload)
                except Exception:
                    pass
            return payload.decode("utf-8", errors="replace").strip()
        return f"[RAW {len(data)}B]"
    except socket.timeout:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"


def connect(host, port):
    print(f"\n  Conectando a {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.settimeout(None)

    # Handshake
    device_xml = (
        '<Command request="998"><parm>'
        '<DeviceName>ReTest</DeviceName>'
        '<DeviceModel>Python</DeviceModel>'
        '<UUID>retest-keys-0000-0000-000000000000</UUID>'
        '</parm></Command>'
    )
    sock.sendall(build_packet(device_xml))
    read_response(sock, 5.0)
    sock.sendall(build_packet('<Command request="32" />'))
    read_response(sock, 5.0)
    sock.sendall(build_packet('<Command request="19" />'))
    read_response(sock, 5.0)
    print("  ✓ Conectado y handshake OK\n")
    return sock


def send_key(sock, kv):
    drain_socket(sock)
    xml = f'<Command request="1040"><parm><KeyValue>{kv}</KeyValue></parm></Command>'
    sock.sendall(build_packet(xml))
    resp = read_response(sock, 2.0)
    time.sleep(0.5)
    return resp


def show_pending(pending):
    sorted_p = sorted(pending)
    for i, btn in enumerate(sorted_p):
        end = "\n" if (i + 1) % 5 == 0 else ""
        print(f"    \033[36m{i+1:2d}\033[0m) {btn:<12}", end=end)
    if len(sorted_p) % 5 != 0:
        print()
    return sorted_p


def ask(sorted_pending):
    print(f"\n     \033[90m 0) Nada   r) Reenviar   q) Siguiente contexto\033[0m")
    raw = input("    → ").strip()
    if not raw or raw == "0":
        return None
    if raw.lower() == "q":
        return "__QUIT__"
    if raw.lower() == "r":
        return "__REENVIAR__"
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(sorted_pending):
            return sorted_pending[idx]
    except ValueError:
        pass
    return raw.upper()


def main():
    contexts = [
        ("CANAL", "Pon un canal de TV (que tenga imagen y audio).\n"
         "  Probaremos: CH_UP, CH_DOWN, INFO, MUTE, EXIT, BACK, REC, FAV, RECALL, 0_NUM..."),
        ("MENU", "Entra en el MENÚ principal del deco (pulsa MENU en el mando).\n"
         "  Probaremos: EXIT, BACK..."),
        ("REPRO", "Si puedes, pon una grabación o timeshift.\n"
         "  Probaremos: PLAY, PAUSE, STOP, FF, REW..."),
    ]

    print("\033[1m")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   Re-test de KeyValues muertos                      ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\033[0m")
    print(f"  {len(DEAD_KEYS)} códigos a re-probar: {DEAD_KEYS}")

    pending = set(PENDING_BUTTONS)
    results: dict[str, str] = {}
    sock = connect(DECO_HOST, DECO_PORT)

    for ctx_name, ctx_instructions in contexts:
        print(f"\n\033[1;33m{'═' * 56}")
        print(f"  CONTEXTO: {ctx_name}")
        print(f"{'═' * 56}\033[0m")
        print(f"  {ctx_instructions}")
        input("\n  Pulsa ENTER cuando estés listo...")

        for kv in DEAD_KEYS:
            if str(kv) in results:
                continue  # ya descubierto en contexto anterior

            # Ping para mantener viva la conexión
            try:
                sock.sendall(build_packet('<Command request="26" />'))
                read_response(sock, 2.0)
            except Exception:
                sock.close()
                sock = connect(DECO_HOST, DECO_PORT)

            send_key(sock, kv)
            print(f"\n  \033[1m[{kv:3d}] KeyValue={kv} enviado\033[0m")

            sorted_p = show_pending(pending)
            answer = ask(sorted_p)

            if answer == "__QUIT__":
                break
            elif answer == "__REENVIAR__":
                send_key(sock, kv)
                print(f"  Re-enviado.")
                sorted_p = show_pending(pending)
                answer = ask(sorted_p)
                if answer and not answer.startswith("__"):
                    results[str(kv)] = answer
                    pending.discard(answer)
                    print(f"  ✓ \033[92m{answer} = KeyValue {kv}\033[0m")
            elif answer is None:
                pass
            else:
                results[str(kv)] = answer
                pending.discard(answer)
                print(f"  ✓ \033[92m{answer} = KeyValue {kv}\033[0m")

        if not pending:
            print("\n  ¡Todos los botones identificados!")
            break

    sock.close()

    # Guardar: merge con el JSON existente
    if OUTPUT_FILE.exists():
        data = json.loads(OUTPUT_FILE.read_text())
    else:
        data = {"new_keys": {}, "all_known": {}}

    data["new_keys"].update(results)
    data["all_known"].update(results)
    data["captured_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    OUTPUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if results:
        print(f"\n\033[1m  DESCUBIERTOS ({len(results)}):\033[0m")
        for code, name in sorted(results.items(), key=lambda x: int(x[0])):
            print(f"    KeyValue {code:>3} = {name}")

    print(f"\n  Guardado en {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
