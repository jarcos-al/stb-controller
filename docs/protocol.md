# Protocolo ALi/G-MScreen — Documentación Técnica

Documentación completa del protocolo propietario TCP utilizado por la aplicación móvil **G-MScreen** para comunicarse con decodificadores satélite basados en chipsets **ALi/Guoxin** (Qviart, Iris, Engel, etc.).

Este protocolo fue descubierto mediante ingeniería inversa utilizando un proxy MITM (`scripts/sniffer.py`) entre un iPhone con la app G-MScreen y un decodificador Qviart Undro/Dual.

## Capa de transporte

- **Protocolo:** TCP
- **Puerto:** 20000
- **Conexiones simultáneas:** Solo **1** — abrir una segunda conexión mata la primera
- **Encoding:** UTF-8 para XML, Little-Endian para campos binarios

## Formato de petición (Cliente → STB)

Las peticiones se envían como cadenas ASCII con la estructura:

```
Start{longitud}End{contenido_xml}
```

- `Start` — Marcador de inicio (literal)
- `{longitud}` — 7 dígitos decimales con zero-padding, longitud del XML completo
- `End` — Marcador de fin del header (literal)
- `{contenido_xml}` — XML con header estándar

### Ejemplo: Ping

```
Start0000080End<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><Command request="26" />
```

### Ejemplo: Pulsación de tecla (OK)

```xml
<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<Command request="1040">
  <parm>
    <KeyValue>5</KeyValue>
  </parm>
</Command>
```

### Ejemplo: Registro de dispositivo (handshake)

```xml
<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<Command request="998">
  <parm>
    <DeviceName>STBControl</DeviceName>
    <DeviceModel>WebPanel</DeviceModel>
    <UUID>stb-control-web-001</UUID>
  </parm>
</Command>
```

## Formato de respuesta (STB → Cliente)

### Respuestas GCDH (estándar)

La mayoría de respuestas usan el formato GCDH:

```
Offset  Tamaño  Contenido
──────  ──────  ─────────
0x00    4B      Firma mágica: "GCDH" (0x47 0x43 0x44 0x48)
0x04    4B      Longitud del payload (uint32 Little-Endian)
0x08    8B      Reservado / padding
0x10    N B     Payload (XML, posiblemente comprimido con zlib)
```

**Total header: 16 bytes.**

### Compresión zlib

Si el payload comienza con `0x78 0x9C`, `0x78 0xDA` o `0x78 0x01`, está comprimido con zlib y debe descomprimirse antes de parsear el XML.

### Respuesta especial: req=998

El registro de dispositivo (request 998) **no usa formato GCDH**. Devuelve exactamente **108 bytes raw** que no contienen información parseable útil.

## Secuencia de handshake

Al conectarse, el cliente debe ejecutar esta secuencia de requests:

```
998 → 32 → 18 → 22 → 20 → 16 → 15
```

| Paso | Request | Contenido de la respuesta |
|------|---------|---------------------------|
| 1 | `998` | Registro del dispositivo (108B raw) |
| 2 | `32` | Info del servidor (URL appstore, device_id, versión) |
| 3 | `18` | Opciones de ordenación de canales |
| 4 | `22` | Lista de satélites configurados |
| 5 | `20` | Estado de bloqueos (parental, instalación, etc.) |
| 6 | `16` | Configuración general (tipo de canal, IP del cliente) |
| 7 | `15` | **Info del STB** (ProductName, SerialNumber, SoftwareVersion) |

### Respuesta de req=15 (Info del STB)

```xml
<Command>
  <parm>
    <StbStatus>1</StbStatus>
    <ProductName>QVIART UNDRO</ProductName>
    <SoftwareVersion>1.18 [03202026]</SoftwareVersion>
    <SerialNumber>210121004929</SerialNumber>
    <ChannelNum>479</ChannelNum>
    <MaxNumOfPrograms>100000</MaxNumOfPrograms>
  </parm>
</Command>
```

## Catálogo de comandos

### Comandos de consulta

| Request ID | Función | Parámetros | Respuesta |
|-----------|---------|------------|-----------|
| `0` | Lista de canales | `FromIndex`, `ToIndex` | Paginado (100 canales/página) |
| `3` | Canal actual | — | `<Data>ProgramId</Data>` |
| `12` | Bouquets | — | Lista de favoritos |
| `15` | Info del STB | — | Nombre, serial, versión, nº canales |
| `16` | Config general | — | Tipo canal, IP cliente |
| `18` | Opciones de orden | — | Tipos de ordenación disponibles |
| `20` | Bloqueos | — | Estado de locks parentales |
| `22` | Satélites | — | Lista de satélites configurados |
| `26` | Ping / keepalive | — | Respuesta vacía (mantiene conexión) |
| `32` | Info servidor | — | URL appstore, device_id |

### Comandos de acción

| Request ID | Función | Parámetros |
|-----------|---------|------------|
| `998` | Registro dispositivo | `DeviceName`, `DeviceModel`, `UUID` |
| `1000` | Zap (cambiar canal) | `ProgramId` del canal destino |
| `1040` | Pulsación de tecla | `KeyValue` numérico |

### Lista de canales (req=0)

Paginación con `FromIndex` / `ToIndex` (bloques de 100):

```xml
<Command request="0">
  <parm>
    <FromIndex>0</FromIndex>
    <ToIndex>99</ToIndex>
  </parm>
</Command>
```

Respuesta con canales:

```xml
<Command>
  <parm>
    <ProgramId>00010000501075</ProgramId>
    <ChannelName>La 1 HD</ChannelName>
    <ChannelType>0</ChannelType>        <!-- 0=TV, 1=Radio -->
    <SatName>Astra1</SatName>
    <Frequency>11229</Frequency>
    <FavGroupList>Astra TV,TDT</FavGroupList>
    <!-- ... más campos -->
  </parm>
  <!-- ... más canales -->
</Command>
```

### Zap (req=1000)

```xml
<Command request="1000">
  <parm>
    <ProgramId>00010000501075</ProgramId>
  </parm>
</Command>
```

## Mapa de teclas (req=1040)

Códigos `KeyValue` descubiertos mediante exploración sistemática:

### Navegación

| KeyValue | Tecla |
|----------|-------|
| 1 | UP |
| 2 | DOWN |
| 3 | LEFT |
| 4 | RIGHT |
| 5 | OK / Enter |

### Menús

| KeyValue | Tecla |
|----------|-------|
| 6 | MENU |
| 7 | EXIT |
| 22 | INFO |
| 29 | BACK |
| 30 | SAT |
| 32 | EPG |
| 34 | TEXT |
| 26 | TIMER |

### Colores

| KeyValue | Tecla |
|----------|-------|
| 8 | RED |
| 9 | GREEN |
| 10 | YELLOW |
| 11 | BLUE |

### Numérico

| KeyValue | Tecla |
|----------|-------|
| 12 | 0 |
| 13 | 1 |
| 14 | 2 |
| 15 | 3 |
| 16 | 4 |
| 17 | 5 |
| 18 | 6 |
| 19 | 7 |
| 20 | 8 |
| 21 | 9 |

### Volumen y canales

| KeyValue | Tecla |
|----------|-------|
| 23 | MUTE |
| 35 | VOL_UP |
| 36 | VOL_DOWN |
| 37 | CH_UP |
| 38 | CH_DOWN |

### Control

| KeyValue | Tecla |
|----------|-------|
| 42 | POWER |
| 31 | SUBTITLE |
| 58 | REC |
| 61 | PLAY |
| 62 | STOP |
| 63 | PAUSE |

## Notas de implementación

### Keepalive

El STB cierra la conexión tras ~30 segundos de inactividad. Enviar `request="26"` periódicamente (cada 5-10s) mantiene la conexión activa.

### Canal actual (req=3)

La respuesta solo contiene el `ProgramId` como texto en `<Data>`. Para obtener el nombre del canal, hay que cruzar con la lista de canales previamente cacheada.

### Filtrado TV/Radio

`ChannelType=0` son canales de TV, `ChannelType=1` son de radio. La interfaz por defecto filtra solo TV.

### Volumen

El protocolo **no expone** el nivel de volumen actual ni el estado de mute del STB. Los comandos `VOL_UP`, `VOL_DOWN` y `MUTE` funcionan como pulsaciones de tecla pero no hay feedback del nivel resultante.

### Descubrimiento de red

No existe un protocolo de descubrimiento UDP/broadcast/multicast. Para encontrar STBs en la red se realiza un scan TCP del puerto 20000 en la subred local, seguido de un handshake rápido (req=998 + req=15) para obtener el nombre y número de serie del dispositivo.
