"""
Explorador de Request IDs del protocolo G-MScreen/ALi.
Envía diferentes request IDs al deco y muestra las respuestas
para descubrir cómo solicitar la lista de canales, EPG, etc.
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
XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"

# Requests ya conocidos
KNOWN_REQUESTS = {
    19: "Status inicial",
    26: "Ping/keepalive",
    32: "Appstore URL",
    998: "Handshake device-id",
    1040: "KeyPress",
}

# Requests típicos en chipsets ALi/Guoxin que podrían devolver canales/datos
# Basado en ingeniería inversa de apps similares (ALiDVBController, GMScreen, etc.)
REQUESTS_TO_TRY = [
    # Sin parámetros — solo <Command request="N" />
    (1, None, "???"),
    (2, None, "???"),
    (3, None, "???"),
    (4, None, "???"),
    (5, None, "???"),
    (6, None, "???"),
    (7, None, "???"),
    (8, None, "???"),
    (9, None, "???"),
    (10, None, "???"),
    (11, None, "???"),
    (12, None, "???"),
    (13, None, "???"),
    (14, None, "???"),
    (15, None, "???"),
    (16, None, "???"),
    (17, None, "???"),
    (18, None, "???"),
    (20, None, "???"),
    (21, None, "???"),
    (22, None, "???"),
    (23, None, "???"),
    (24, None, "???"),
    (25, None, "???"),
    (27, None, "???"),
    (28, None, "???"),
    (29, None, "???"),
    (30, None, "???"),
    (31, None, "???"),
    (33, None, "???"),
    (34, None, "???"),
    (35, None, "???"),
    # Rangos comunes en ALi
    (100, None, "???"),
    (101, None, "???"),
    (102, None, "???"),
    (103, None, "???"),
    (104, None, "???"),
    (105, None, "???"),
    (200, None, "???"),
    (201, None, "???"),
    (300, None, "???"),
    (1000, None, "???"),
    (1001, None, "Channel list?"),
    (1002, None, "Bouquet list?"),
    (1003, None, "???"),
    (1004, None, "???"),
    (1005, None, "EPG?"),
    (1006, None, "???"),
    (1007, None, "???"),
    (1008, None, "???"),
    (1009, None, "???"),
    (1010, None, "???"),
    (1011, None, "???"),
    (1012, None, "???"),
    (1020, None, "???"),
    (1021, None, "???"),
    (1030, None, "???"),
    (1031, None, "???"),
    (1035, None, "???"),
    (1041, None, "???"),
    (1042, None, "???"),
    (1043, None, "???"),
    (1044, None, "???"),
    (1045, None, "???"),
    (1050, None, "???"),
    (1051, None, "???"),
    (1060, None, "???"),
    (1070, None, "???"),
    (1080, None, "???"),
    (1090, None, "???"),
    (1100, None, "???"),
    (2000, None, "???"),
    (2001, None, "???"),
    (3000, None, "???"),
    (9999, None, "???"),
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


def read_response_raw(sock, timeout=5.0) -> tuple[str, int]:
    """Lee respuesta y devuelve (texto, tamaño_bytes)."""
    sock.settimeout(timeout)
    try:
        data = sock.recv(4096)
        if not data:
            return "[sin respuesta]", 0

        # GCDH
        if data[:4] == b'GCDH' and len(data) >= 16:
            payload_len = struct.unpack_from('<I', data, 4)[0]
            payload = data[16:16 + payload_len]
            while len(payload) < payload_len:
                more = sock.recv(4096)
                if not more:
                    break
                payload += more
            payload = payload[:payload_len]
            raw_size = len(payload)

            if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
                try:
                    payload = zlib.decompress(payload)
                except Exception:
                    pass

            return payload.decode("utf-8", errors="replace").strip(), raw_size
        else:
            return f"[RAW {len(data)}B] {data[:50]}", len(data)
    except socket.timeout:
        return "[timeout]", 0
    except Exception as e:
        return f"[error: {e}]", 0


def connect(host, port):
    print(f"\n  Conectando a {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.settimeout(None)

    # Handshake
    device_xml = (
        '<Command request="998"><parm>'
        '<DeviceName>Explorer</DeviceName>'
        '<DeviceModel>Python</DeviceModel>'
        '<UUID>explore-req-0000-0000-000000000000</UUID>'
        '</parm></Command>'
    )
    sock.sendall(build_packet(device_xml))
    read_response_raw(sock, 5.0)
    sock.sendall(build_packet('<Command request="32" />'))
    read_response_raw(sock, 5.0)
    sock.sendall(build_packet('<Command request="19" />'))
    read_response_raw(sock, 5.0)
    print("  ✓ Conectado\n")
    return sock


def main():
    print("\033[1m")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   G-MScreen — Explorador de Request IDs             ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\033[0m")

    sock = connect(DECO_HOST, DECO_PORT)
    results = {}
    ping_count = 0

    for req_id, params, desc in REQUESTS_TO_TRY:
        if req_id in KNOWN_REQUESTS:
            print(f"  [{req_id:5d}] \033[90m{KNOWN_REQUESTS[req_id]} (ya conocido, skip)\033[0m")
            continue

        ping_count += 1
        if ping_count % 10 == 0:
            try:
                sock.sendall(build_packet('<Command request="26" />'))
                read_response_raw(sock, 2.0)
            except Exception:
                sock.close()
                sock = connect(DECO_HOST, DECO_PORT)

        drain_socket(sock)

        if params:
            xml = f'<Command request="{req_id}"><parm>{params}</parm></Command>'
        else:
            xml = f'<Command request="{req_id}" />'

        try:
            sock.sendall(build_packet(xml))
        except Exception:
            sock.close()
            sock = connect(DECO_HOST, DECO_PORT)
            sock.sendall(build_packet(xml))

        resp, size = read_response_raw(sock, 5.0)
        time.sleep(0.3)

        # Colorear según resultado
        if resp == "[timeout]" or resp == "[sin respuesta]":
            color = "\033[90m"  # gris
            tag = "✗"
        elif "error" in resp.lower():
            color = "\033[91m"  # rojo
            tag = "✗"
        else:
            color = "\033[92m"  # verde
            tag = "✓"
            results[req_id] = {"response": resp[:500], "size": size}

        # Truncar para display
        display = resp[:120].replace('\n', ' ')
        print(f"  [{req_id:5d}] {color}{tag} {display}\033[0m")

        if size > 200:
            print(f"         \033[93m↑ Respuesta larga: {size}B comprimido, {len(resp)}B descomprimido\033[0m")

    sock.close()

    # Guardar resultados
    output = Path("gmscreen_requests_explored.json")
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"\n\033[1m  Requests que respondieron: {len(results)}\033[0m")
    for req_id, info in sorted(results.items()):
        print(f"    req={req_id:5d}  ({info['size']}B)  {info['response'][:80]}")

    print(f"\n  Guardado en {output}\n")


if __name__ == "__main__":
    main()
