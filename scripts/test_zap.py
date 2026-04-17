#!/usr/bin/env python3
"""Test req=1000 as ZAP command"""
import socket, struct, zlib, time

DECO = '192.168.50.37'
XML_HEADER = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>"

def build_packet(xml_body):
    full_xml = f'{XML_HEADER}{xml_body}'
    length_str = str(len(full_xml)).zfill(7)
    return f'Start{length_str}End{full_xml}'.encode('utf-8')

def read_gcdh(sock, timeout=5.0):
    sock.settimeout(timeout)
    try:
        header = b''
        while len(header) < 16:
            chunk = sock.recv(16 - len(header))
            if not chunk: return ''
            header += chunk
        if not header.startswith(b'GCDH'):
            return f'[RAW {len(header)}B]'
        plen = struct.unpack_from('<I', header, 4)[0]
        payload = b''
        while len(payload) < plen:
            chunk = sock.recv(min(4096, plen - len(payload)))
            if not chunk: break
            payload += chunk
        if payload.startswith((b'\x78\x9c', b'\x78\xda', b'\x78\x01')):
            payload = zlib.decompress(payload)
        return payload.decode('utf-8', errors='replace').strip()
    except:
        return '[timeout]'

def drain(sock):
    sock.setblocking(False)
    try:
        while True:
            d = sock.recv(4096)
            if not d: break
    except BlockingIOError:
        pass
    finally:
        sock.setblocking(True)

def read_raw(sock, timeout=5.0):
    sock.settimeout(timeout)
    try:
        return sock.recv(4096)
    except:
        return b''

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect((DECO, 20000))

# Handshake
sock.sendall(build_packet('<Command request="998"><parm><DeviceName>ZapTest</DeviceName><DeviceModel>Python</DeviceModel><UUID>zap-test-0001</UUID></parm></Command>'))
read_raw(sock, 5)
time.sleep(0.2)
sock.sendall(build_packet('<Command request="32" />'))
read_gcdh(sock, 5)
for r in [18, 22, 20, 16, 15]:
    time.sleep(0.2)
    sock.sendall(build_packet(f'<Command request="{r}" />'))
    read_gcdh(sock, 5)

# Check current channel
time.sleep(0.3)
drain(sock)
sock.sendall(build_packet('<Command request="3" />'))
before = read_gcdh(sock, 5)
print(f'ANTES: {before}')

# ZAP with req=1000
target = '00010000800041'  # LALIGA TV BAR
print(f'\nZAP req=1000 -> {target}')
time.sleep(0.3)
drain(sock)
zap_xml = (
    f'<Command request="1000"><parm>'
    f'<TvState>0</TvState>'
    f'<ProgramId>{target}</ProgramId>'
    f'<iResolutionRatio>0</iResolutionRatio>'
    f'<iBitrate>0</iBitrate>'
    f'</parm></Command>'
)
sock.sendall(build_packet(zap_xml))
resp = read_gcdh(sock, 5)
print(f'Respuesta: {resp}')

# Verify
time.sleep(1)
drain(sock)
sock.sendall(build_packet('<Command request="3" />'))
after = read_gcdh(sock, 5)
print(f'\nDESPUES: {after}')

if target in str(after):
    print('\n*** ZAP EXITOSO! req=1000 es el comando de cambio de canal ***')
else:
    print('\nNo cambio al target')

sock.close()
