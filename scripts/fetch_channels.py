"""
Descarga la lista completa de canales del decodificador G-MScreen.
Protocolo: req=0 con FromIndex/ToIndex, paginado de 100 en 100.

Uso:
    python fetch_channels.py [--host 192.168.50.37] [--output channels.json]
"""

import socket
import struct
import zlib
import json
import time
import re
import sys
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET

DECO_HOST = "192.168.50.37"
DECO_PORT = 20000
XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"
PAGE_SIZE = 100


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


def read_response(sock, timeout=10.0) -> str:
    """Lee respuesta GCDH completa."""
    sock.settimeout(timeout)
    try:
        # Leer header 16 bytes
        header = b''
        while len(header) < 16:
            chunk = sock.recv(16 - len(header))
            if not chunk:
                return ""
            header += chunk

        if not header.startswith(b'GCDH'):
            return f"[RAW {len(header)}B]"

        payload_len = struct.unpack_from('<I', header, 4)[0]

        # Leer payload completo
        payload = b''
        while len(payload) < payload_len:
            chunk = sock.recv(min(4096, payload_len - len(payload)))
            if not chunk:
                break
            payload += chunk

        # Descomprimir zlib
        if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
            try:
                payload = zlib.decompress(payload)
            except Exception:
                pass

        return payload.decode("utf-8", errors="replace").strip()
    except socket.timeout:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"


def read_raw_response(sock, timeout=5.0) -> bytes:
    """Lee respuesta RAW (para req=998 que no usa GCDH)."""
    sock.settimeout(timeout)
    try:
        data = sock.recv(4096)
        return data if data else b''
    except socket.timeout:
        return b''
    except Exception:
        return b''


def connect(host, port):
    print(f"  Conectando a {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.settimeout(None)

    # Handshake req=998 — respuesta RAW 108 bytes (NO es GCDH)
    device_xml = (
        '<Command request="998"><parm>'
        '<DeviceName>ChannelFetch</DeviceName>'
        '<DeviceModel>Python</DeviceModel>'
        '<UUID>channels-0000-0000-000000000000</UUID>'
        '</parm></Command>'
    )
    sock.sendall(build_packet(device_xml))
    raw = read_raw_response(sock, 5.0)
    print(f"    req=998: RAW {len(raw)}B")

    # req=32 — appstore URL (GCDH)
    time.sleep(0.2)
    drain_socket(sock)
    sock.sendall(build_packet('<Command request="32" />'))
    resp = read_response(sock, 5.0)
    print(f"    req=32: {resp[:60]}")

    # Enviar misma secuencia que la app real
    for req_id in [18, 22, 20, 16, 15]:
        time.sleep(0.2)
        drain_socket(sock)
        sock.sendall(build_packet(f'<Command request="{req_id}" />'))
        resp = read_response(sock, 5.0)
        print(f"    req={req_id}: {resp[:80]}")

    print("  ✓ Conectado\n")
    return sock


def fetch_stb_info(sock) -> dict:
    """Obtiene info del STB (req=15)."""
    drain_socket(sock)
    sock.sendall(build_packet('<Command request="15" />'))
    resp = read_response(sock, 5.0)
    info = {}
    try:
        # Extraer el XML del Command
        xml_match = re.search(r'<parm>(.*?)</parm>', resp, re.DOTALL)
        if xml_match:
            parm_xml = f"<parm>{xml_match.group(1)}</parm>"
            root = ET.fromstring(parm_xml)
            for child in root:
                info[child.tag] = child.text
    except Exception:
        info["raw"] = resp[:200]
    return info


def fetch_satellites(sock) -> list[dict]:
    """Obtiene lista de satélites (req=22)."""
    drain_socket(sock)
    sock.sendall(build_packet('<Command request="22" />'))
    resp = read_response(sock, 5.0)
    sats = []
    try:
        # Puede haber múltiples satélites en la respuesta
        for match in re.finditer(r'<SatName>(.*?)</SatName>.*?<SatNo>(.*?)</SatNo>.*?<SatAngl[e]?>(.*?)</SatAngl', resp, re.DOTALL):
            sats.append({
                "name": match.group(1),
                "number": match.group(2),
                "angle": match.group(3),
            })
    except Exception:
        pass
    return sats


def fetch_current_channel(sock) -> str:
    """Obtiene el canal actual (req=3)."""
    drain_socket(sock)
    sock.sendall(build_packet('<Command request="3" />'))
    resp = read_response(sock, 5.0)
    match = re.search(r'<Data>(.*?)</Data>', resp)
    return match.group(1) if match else ""


def parse_channels_xml(xml_str: str) -> list[dict]:
    """Parsea la respuesta XML de canales y extrae los campos."""
    channels = []

    # La respuesta tiene múltiples canales dentro de <parm>
    # Cada canal tiene: ProgramId, ProgramName, y posiblemente más campos
    # Formato: <parm><ProgramId>X</ProgramId><ProgramName>Y</ProgramName>...
    #          <ProgramId>X2</ProgramId><ProgramName>Y2</ProgramName>...</parm>

    # Extraer contenido del parm
    parm_match = re.search(r'<parm>(.*)</parm>', xml_str, re.DOTALL)
    if not parm_match:
        return channels

    content = parm_match.group(1)

    # Dividir por ProgramId (cada canal empieza con un ProgramId)
    parts = re.split(r'(?=<ProgramId>)', content)

    for part in parts:
        if not part.strip():
            continue

        channel = {}
        # Extraer todos los tags XML
        for tag_match in re.finditer(r'<(\w+)>(.*?)</\1>', part):
            tag_name = tag_match.group(1)
            tag_value = tag_match.group(2)
            channel[tag_name] = tag_value

        if "ProgramId" in channel:
            channels.append(channel)

    return channels


def fetch_channel_list(sock) -> list[dict]:
    """Descarga la lista completa de canales paginando de 100 en 100."""
    all_channels = []
    from_idx = 0

    while True:
        to_idx = from_idx + PAGE_SIZE - 1
        drain_socket(sock)

        xml = (
            f'<Command request="0"><parm>'
            f'<FromIndex>{from_idx}</FromIndex>'
            f'<ToIndex>{to_idx}</ToIndex>'
            f'</parm></Command>'
        )
        sock.sendall(build_packet(xml))
        resp = read_response(sock, 10.0)

        if resp.startswith("[") or not resp:
            print(f"    [{from_idx:4d}-{to_idx:4d}] Sin respuesta, fin de lista")
            break

        channels = parse_channels_xml(resp)

        if not channels:
            print(f"    [{from_idx:4d}-{to_idx:4d}] 0 canales, fin de lista")
            break

        all_channels.extend(channels)
        print(f"    [{from_idx:4d}-{to_idx:4d}] {len(channels)} canales (total: {len(all_channels)})")

        # Si devolvió menos de PAGE_SIZE, es la última página
        if len(channels) < PAGE_SIZE:
            break

        from_idx += PAGE_SIZE
        time.sleep(0.3)

    return all_channels


def main():
    parser = argparse.ArgumentParser(description="Descarga lista de canales G-MScreen")
    parser.add_argument("--host", default=DECO_HOST)
    parser.add_argument("--port", type=int, default=DECO_PORT)
    parser.add_argument("--output", default="channels.json")
    args = parser.parse_args()

    print("\033[1m")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   G-MScreen — Descarga de lista de canales          ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\033[0m")

    sock = connect(args.host, args.port)

    # Info del STB
    print("  \033[1mInfo del STB (req=15):\033[0m")
    stb_info = fetch_stb_info(sock)
    for k, v in stb_info.items():
        print(f"    {k}: {v}")

    # Satélites
    print("\n  \033[1mSatélites (req=22):\033[0m")
    sats = fetch_satellites(sock)
    for sat in sats:
        print(f"    {sat['name']} (#{sat['number']}, {sat['angle']}°)")

    # Canal actual
    print("\n  \033[1mCanal actual (req=3):\033[0m")
    current = fetch_current_channel(sock)
    print(f"    ProgramId: {current}")

    # Lista de canales
    print("\n  \033[1mDescargando canales (req=0):\033[0m")
    channels = fetch_channel_list(sock)

    sock.close()

    # Guardar
    output = {
        "stb_info": stb_info,
        "satellites": sats,
        "current_channel": current,
        "total_channels": len(channels),
        "channels": channels,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # Resumen
    print(f"\n  \033[1m{'═' * 50}\033[0m")
    print(f"  \033[92m{len(channels)} canales descargados\033[0m")
    print(f"  Guardado en: {output_path.resolve()}")

    # Mostrar primeros 20
    print(f"\n  \033[1mPrimeros 20 canales:\033[0m")
    for i, ch in enumerate(channels[:20]):
        name = ch.get("ProgramName", "???")
        pid = ch.get("ProgramId", "")
        print(f"    {i+1:4d}. {name:<30} [{pid}]")

    if len(channels) > 20:
        print(f"    ... y {len(channels) - 20} más")

    print()


if __name__ == "__main__":
    main()
