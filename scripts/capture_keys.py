"""
Captura libre de teclas G-MScreen
==================================
Monitor en tiempo real del event log del sniffer. NO es guiado paso a paso.
Tú pulsas un botón en el iPhone, el script detecta el KeyValue nuevo,
y tú le dices qué botón era. Funciona aunque el iPhone se reconecte.

Uso:
    1. python sniffer.py          (terminal 1)
    2. python capture_keys.py     (terminal 2)
    3. Conecta el iPhone al sniffer
    4. Pulsa un botón → el script pregunta qué era → repite
    5. Escribe "fin" para terminar y generar el mapa
"""

import re
import json
import time
import sys
from pathlib import Path

EVENT_LOG = Path("/tmp/gmscreen_events.log")
OUTPUT_FILE = Path("gmscreen_keymap_captured.json")

# Nombres sugeridos para autocompletar
KNOWN_NAMES = [
    "UP", "DOWN", "LEFT", "RIGHT", "OK",
    "MENU", "EXIT", "INFO", "EPG", "BACK",
    "VOL_UP", "VOL_DOWN", "MUTE",
    "CH_UP", "CH_DOWN",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "RED", "GREEN", "YELLOW", "BLUE",
    "PLAY", "PAUSE", "STOP", "REW", "FF", "REC",
    "POWER",
]

_RE_KEY = re.compile(r'KeyValue=(\d+)')


def wait_for_key(offset: int) -> tuple[str, int]:
    """
    Espera hasta que aparezca un nuevo KeyValue en el event log.
    Devuelve (código, nuevo_offset). Espera indefinidamente.
    """
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    spin_i = 0

    while True:
        try:
            size = EVENT_LOG.stat().st_size
        except FileNotFoundError:
            time.sleep(0.3)
            continue

        if size > offset:
            with open(EVENT_LOG, "r", errors="replace") as f:
                f.seek(offset)
                new_data = f.read()
            new_offset = offset + len(new_data.encode())

            # Puede haber múltiples events — tomar el último
            matches = list(_RE_KEY.finditer(new_data))
            if matches:
                code = matches[-1].group(1)
                return code, new_offset
            offset = new_offset

        # Spinner animado
        print(f"\r  {spinner[spin_i]} Esperando pulsación en iPhone...", end="", flush=True)
        spin_i = (spin_i + 1) % len(spinner)
        time.sleep(0.2)


def main():
    print("\033[1m")
    print("╔══════════════════════════════════════════════════════╗")
    print("║   G-MScreen — Captura Libre de Teclas               ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("\033[0m")
    print("  Modo: pulsa un botón en el iPhone, di qué botón era.")
    print("  Escribe \033[93mfin\033[0m para terminar y generar el mapa.")
    print("  Escribe \033[93mskip\033[0m para ignorar una pulsación.")
    print()
    print("  Requisitos:")
    print("    ✓ sniffer.py corriendo")
    print("    ✓ iPhone conectado a G-MScreen (vía sniffer)")
    print()
    print(f"  Nombres válidos: {', '.join(KNOWN_NAMES[:12])}...")
    print()

    if not EVENT_LOG.exists():
        print("\033[91m  ✗ No se encuentra /tmp/gmscreen_events.log\033[0m")
        print("    Ejecuta primero: python sniffer.py")
        sys.exit(1)

    captured: dict[str, str] = {}  # nombre → código
    count = 0

    # Empezar desde el final del log actual (ignorar eventos viejos)
    offset = EVENT_LOG.stat().st_size

    print("  ¡Listo! Pulsa botones en el iPhone cuando quieras.\n")

    try:
        while True:
            code, offset = wait_for_key(offset)
            count += 1

            # Limpiar la línea del spinner
            print(f"\r\033[K", end="")

            # Comprobar si ya lo tenemos mapeado
            existing = None
            for name, val in captured.items():
                if val == code:
                    existing = name
                    break

            if existing:
                print(f"  🔄 KeyValue={code} ya mapeado como \033[92m{existing}\033[0m (repetido)")
                continue

            print(f"  🎮 \033[1mDetectado KeyValue={code}\033[0m")
            name = input(f"     ¿Qué botón pulsaste? (o skip/fin): ").strip().upper()

            if name == "FIN":
                break
            elif name == "SKIP" or name == "":
                print(f"     ⏭ Saltado\n")
                continue
            else:
                captured[name] = code
                print(f"     ✓ \033[92m{name} = KeyValue {code}\033[0m\n")

    except KeyboardInterrupt:
        print("\n")

    # ── Resumen ──
    if not captured:
        print("\n  No se capturó ninguna tecla.")
        sys.exit(0)

    print("\033[1m")
    print("═══════════════════════════════════════════════════════")
    print("  RESULTADO DE LA CAPTURA")
    print("═══════════════════════════════════════════════════════")
    print("\033[0m")

    print(f"  Capturadas: \033[92m{len(captured)}\033[0m")
    print(f"  Pulsaciones totales: {count}")
    print()

    print("  \033[1mMapa de teclas:\033[0m")
    print(f"  {'Nombre':<15} {'KeyValue':<10}")
    print(f"  {'─'*15} {'─'*10}")
    for name, code in sorted(captured.items(), key=lambda x: int(x[1])):
        print(f"  {name:<15} {code}")

    # ── Generar código para gmscreen.py ──
    print("\n\033[1m  Fragmento para gmscreen.py:\033[0m")
    print("  ─────────────────────────────")
    print("  GMSCREEN_KEYS = {")
    for name, code in sorted(captured.items(), key=lambda x: int(x[1])):
        print(f'      "{name}": "{code}",')
    print("  }")

    # ── Guardar JSON ──
    result = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "keys": captured,
    }
    OUTPUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n  \033[96mGuardado en: {OUTPUT_FILE.resolve()}\033[0m\n")

    # ── Teclas pendientes ──
    mapped = set(captured.keys())
    pending = [n for n in KNOWN_NAMES if n not in mapped]
    if pending:
        print(f"  \033[93mPendientes: {', '.join(pending)}\033[0m\n")


if __name__ == "__main__":
    main()
