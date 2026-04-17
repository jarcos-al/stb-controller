"""
Mock STB Adapter for development and testing.
Simulates a fully functional STB with procedurally generated data.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional

from backend.adapters.base import STBAdapter
from backend.models.schemas import (
    STBStatus,
    KeyPressResponse,
    Channel,
    Bouquet,
    ZapResponse,
    EPGEvent,
    EPGNowNext,
    Timer,
    TimerResponse,
    VolumeState,
    DiscoveredDevice,
)
from backend.core.logging import get_logger

log = get_logger("mock_adapter")

# ──── Mock Data ────

MOCK_PROVIDERS = ["Movistar+", "Astra", "SES", "Eutelsat", "Hispasat"]

MOCK_CHANNELS = {
    "Favoritos": [
        ("La 1 HD", "1:0:19:1001:1:1:C00000:0:0:0:", "RTVE", True),
        ("La 2 HD", "1:0:19:1002:1:1:C00000:0:0:0:", "RTVE", True),
        ("Antena 3 HD", "1:0:19:1003:1:1:C00000:0:0:0:", "Atresmedia", True),
        ("Cuatro HD", "1:0:19:1004:1:1:C00000:0:0:0:", "Mediaset", True),
        ("Telecinco HD", "1:0:19:1005:1:1:C00000:0:0:0:", "Mediaset", True),
        ("La Sexta HD", "1:0:19:1006:1:1:C00000:0:0:0:", "Atresmedia", True),
        ("TVE 24h", "1:0:19:1007:1:1:C00000:0:0:0:", "RTVE", True),
        ("Neox HD", "1:0:19:1008:1:1:C00000:0:0:0:", "Atresmedia", True),
        ("FDF", "1:0:19:1009:1:1:C00000:0:0:0:", "Mediaset", False),
        ("Energy", "1:0:19:1010:1:1:C00000:0:0:0:", "Mediaset", False),
    ],
    "Deportes": [
        ("Movistar LaLiga HD", "1:0:19:2001:1:1:C00000:0:0:0:", "Movistar+", True),
        ("Movistar Liga de Campeones HD", "1:0:19:2002:1:1:C00000:0:0:0:", "Movistar+", True),
        ("DAZN 1 HD", "1:0:19:2003:1:1:C00000:0:0:0:", "DAZN", True),
        ("DAZN 2 HD", "1:0:19:2004:1:1:C00000:0:0:0:", "DAZN", True),
        ("Eurosport 1 HD", "1:0:19:2005:1:1:C00000:0:0:0:", "Eurosport", True),
        ("Teledeporte", "1:0:19:2006:1:1:C00000:0:0:0:", "RTVE", False),
        ("GOL Play", "1:0:19:2007:1:1:C00000:0:0:0:", "Mediapro", False),
    ],
    "Cine": [
        ("Movistar Estrenos HD", "1:0:19:3001:1:1:C00000:0:0:0:", "Movistar+", True),
        ("Movistar Acción HD", "1:0:19:3002:1:1:C00000:0:0:0:", "Movistar+", True),
        ("Movistar Comedia HD", "1:0:19:3003:1:1:C00000:0:0:0:", "Movistar+", True),
        ("TNT HD", "1:0:19:3004:1:1:C00000:0:0:0:", "Warner", True),
        ("AMC HD", "1:0:19:3005:1:1:C00000:0:0:0:", "AMC Networks", True),
        ("Sundance TV", "1:0:19:3006:1:1:C00000:0:0:0:", "AMC Networks", False),
        ("TCM", "1:0:19:3007:1:1:C00000:0:0:0:", "Warner", False),
        ("COSMO", "1:0:19:3008:1:1:C00000:0:0:0:", "NBCUniversal", False),
    ],
    "Infantil": [
        ("Disney Channel HD", "1:0:19:4001:1:1:C00000:0:0:0:", "Disney", True),
        ("Boing", "1:0:19:4002:1:1:C00000:0:0:0:", "Warner", False),
        ("Clan", "1:0:19:4003:1:1:C00000:0:0:0:", "RTVE", False),
        ("Nick Jr", "1:0:19:4004:1:1:C00000:0:0:0:", "Paramount", False),
        ("Baby TV", "1:0:19:4005:1:1:C00000:0:0:0:", "Fox", False),
    ],
    "Documentales": [
        ("Discovery HD", "1:0:19:5001:1:1:C00000:0:0:0:", "Discovery", True),
        ("National Geographic HD", "1:0:19:5002:1:1:C00000:0:0:0:", "NatGeo", True),
        ("Historia HD", "1:0:19:5003:1:1:C00000:0:0:0:", "A&E", True),
        ("#0 HD", "1:0:19:5004:1:1:C00000:0:0:0:", "Movistar+", True),
        ("Odisea", "1:0:19:5005:1:1:C00000:0:0:0:", "Chello", False),
        ("DMAX", "1:0:19:5006:1:1:C00000:0:0:0:", "Discovery", False),
    ],
}

MOCK_PROGRAMS = [
    "Telediario", "Informativos", "Antena 3 Noticias", "El Hormiguero",
    "La Resistencia", "Pasapalabra", "Tu cara me suena", "MasterChef",
    "Supervivientes", "Sálvame", "El Chiringuito", "Cine de acción",
    "Cine comedia", "Documental: Naturaleza", "Documental: Historia",
    "Fútbol: LaLiga", "Copa del Rey", "Liga de Campeones", "NBA",
    "Cuentos infantiles", "Dibujos animados", "Sesión de tarde",
    "Noche de cine", "Thriller: Investigación", "Serie: Drama policial",
    "Magazine matinal", "Debate político", "Hora Punta", "Espejo Público",
    "Al Rojo Vivo", "La Sexta Noche", "Planeta Calleja", "Salvados",
]


class MockAdapter(STBAdapter):
    """
    Mock adapter that simulates a fully functional STB.
    Used for development and testing without real hardware.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0, **kwargs):
        super().__init__(host, port, **kwargs)
        self._volume = 50
        self._muted = False
        self._standby = False
        self._current_channel_idx = 0
        self._all_channels = self._build_channel_list()
        self._timers: list[dict] = self._generate_mock_timers()
        self._timer_id_counter = len(self._timers) + 1
        log.info("mock_adapter_created", host=host)

    def _build_channel_list(self) -> list[tuple]:
        """Build a flat list of all channels."""
        channels = []
        for bouquet_name, bouquet_channels in MOCK_CHANNELS.items():
            for ch in bouquet_channels:
                channels.append(ch)
        return channels

    def _generate_mock_epg(self, channel_name: str, service_ref: str, count: int = 10) -> list[EPGEvent]:
        """Generate procedural EPG data for a channel."""
        events = []
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        # Start from 2 hours ago
        current_time = now - timedelta(hours=2)

        for i in range(count):
            duration = random.choice([30, 45, 60, 90, 120]) * 60  # in seconds
            program = random.choice(MOCK_PROGRAMS)
            events.append(EPGEvent(
                event_id=random.randint(10000, 99999),
                title=program,
                description=f"Descripción de {program} en {channel_name}.",
                description_ext=f"Información extendida sobre la emisión de {program}. "
                                f"Temporada {random.randint(1, 10)}, Episodio {random.randint(1, 24)}.",
                start_time=current_time.isoformat(),
                duration=duration,
                service_ref=service_ref,
                channel_name=channel_name,
                genre=random.choice(["Movie", "News", "Sports", "Kids", "Documentary", "Series", "Entertainment"]),
            ))
            current_time += timedelta(seconds=duration)

        return events

    def _generate_mock_timers(self) -> list[dict]:
        """Generate some sample timers."""
        now = datetime.now()
        return [
            {
                "id": 1,
                "service_ref": "1:0:19:1001:1:1:C00000:0:0:0:",
                "channel_name": "La 1 HD",
                "begin_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": (now + timedelta(hours=3)).isoformat(),
                "name": "Telediario 21:00",
                "description": "Grabación automática del Telediario nocturno",
                "state": 0,
                "repeated": 0,
                "repeated_days": "",
            },
            {
                "id": 2,
                "service_ref": "1:0:19:2001:1:1:C00000:0:0:0:",
                "channel_name": "Movistar LaLiga HD",
                "begin_time": (now + timedelta(days=1, hours=5)).isoformat(),
                "end_time": (now + timedelta(days=1, hours=7)).isoformat(),
                "name": "Fútbol: LaLiga Jornada 30",
                "description": "Partido de liga",
                "state": 0,
                "repeated": 0,
                "repeated_days": "",
            },
        ]

    # ──── Connection ────

    async def connect(self) -> bool:
        await asyncio.sleep(0.1)  # Simulate connection delay
        self._connected = True
        log.info("mock_connected")
        return True

    async def disconnect(self):
        self._connected = False
        log.info("mock_disconnected")

    async def check_health(self) -> bool:
        return self._connected

    # ──── Status ────

    async def get_status(self) -> STBStatus:
        if not self._all_channels:
            return STBStatus(device_name="Mock STB", device_model="MockBox 4K")

        ch = self._all_channels[self._current_channel_idx]
        ch_name, ch_ref, provider, is_hd = ch

        # Generate current EPG
        epg = self._generate_mock_epg(ch_name, ch_ref, 3)
        now_program = epg[1] if len(epg) > 1 else None

        return STBStatus(
            in_standby=self._standby,
            current_channel=ch_name,
            current_channel_ref=ch_ref,
            current_program=now_program.title if now_program else "Sin información",
            program_description=now_program.description if now_program else "",
            program_start=now_program.start_time if now_program else None,
            program_end=(datetime.fromisoformat(now_program.start_time) + timedelta(seconds=now_program.duration)).isoformat() if now_program else None,
            volume=self._volume,
            is_muted=self._muted,
            is_recording=False,
            signal_strength=random.randint(75, 95),
            signal_snr=random.randint(80, 98),
            device_name="Mock STB",
            device_model="MockBox 4K Ultra",
        )

    # ──── Remote Control ────

    KEY_MAP = {
        "POWER": "power", "OK": "ok", "ENTER": "ok",
        "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
        "MENU": "menu", "EXIT": "exit", "BACK": "back",
        "VOL_UP": "vol_up", "VOL_DOWN": "vol_down", "MUTE": "mute",
        "CH_UP": "ch_up", "CH_DOWN": "ch_down",
        "EPG": "epg", "INFO": "info",
        "RED": "red", "GREEN": "green", "YELLOW": "yellow", "BLUE": "blue",
        "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
        "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
        "PLAY": "play", "PAUSE": "pause", "STOP": "stop",
        "REC": "rec", "FF": "ff", "REW": "rew",
    }

    async def send_key(self, key: str, key_type: str = "short") -> KeyPressResponse:
        key_upper = key.upper()
        if key_upper not in self.KEY_MAP:
            return KeyPressResponse(result=False, message=f"Unknown key: {key}")

        action = self.KEY_MAP[key_upper]

        # Simulate side effects
        if action == "power":
            self._standby = not self._standby
        elif action == "vol_up":
            self._volume = min(100, self._volume + 5)
        elif action == "vol_down":
            self._volume = max(0, self._volume - 5)
        elif action == "mute":
            self._muted = not self._muted
        elif action == "ch_up":
            self._current_channel_idx = (self._current_channel_idx + 1) % len(self._all_channels)
        elif action == "ch_down":
            self._current_channel_idx = (self._current_channel_idx - 1) % len(self._all_channels)

        log.debug("mock_key_sent", key=key, action=action, key_type=key_type)
        return KeyPressResponse(result=True, message=f"Key '{key}' sent ({key_type})")

    # ──── Channels ────

    async def get_bouquets(self) -> list[Bouquet]:
        bouquets = []
        for i, (name, channels) in enumerate(MOCK_CHANNELS.items()):
            bouquet_ref = f"1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"userbouquet.{name.lower()}.tv\""
            bouquets.append(Bouquet(
                id=i + 1,
                name=name,
                service_ref=bouquet_ref,
            ))
        return bouquets

    async def get_channels(self, bouquet_ref: Optional[str] = None) -> list[Channel]:
        channels = []
        ch_number = 1

        if bouquet_ref:
            # Find matching bouquet
            for name, chs in MOCK_CHANNELS.items():
                if name.lower() in bouquet_ref.lower():
                    for ch_name, ch_ref, provider, is_hd in chs:
                        channels.append(Channel(
                            name=ch_name,
                            service_ref=ch_ref,
                            provider=provider,
                            is_hd=is_hd,
                            channel_number=ch_number,
                        ))
                        ch_number += 1
                    break
        else:
            # Return all channels
            for name, chs in MOCK_CHANNELS.items():
                for ch_name, ch_ref, provider, is_hd in chs:
                    channels.append(Channel(
                        name=ch_name,
                        service_ref=ch_ref,
                        provider=provider,
                        is_hd=is_hd,
                        channel_number=ch_number,
                    ))
                    ch_number += 1

        return channels

    async def zap(self, service_ref: str) -> ZapResponse:
        for i, (ch_name, ch_ref, _, _) in enumerate(self._all_channels):
            if ch_ref == service_ref:
                self._current_channel_idx = i
                log.info("mock_zap", channel=ch_name)
                return ZapResponse(result=True, message=f"Zapped to {ch_name}", channel_name=ch_name)

        return ZapResponse(result=False, message=f"Channel not found: {service_ref}")

    # ──── EPG ────

    async def get_epg_now_next(self, bouquet_ref: Optional[str] = None) -> list[EPGNowNext]:
        channels = await self.get_channels(bouquet_ref)
        result = []

        for ch in channels:
            epg = self._generate_mock_epg(ch.name, ch.service_ref, 3)
            now_event = epg[1] if len(epg) > 1 else None
            next_event = epg[2] if len(epg) > 2 else None
            result.append(EPGNowNext(
                channel_name=ch.name,
                service_ref=ch.service_ref,
                now=now_event,
                next=next_event,
            ))

        return result

    async def get_epg_service(self, service_ref: str) -> list[EPGEvent]:
        ch_name = "Unknown"
        for name, ref, _, _ in self._all_channels:
            if ref == service_ref:
                ch_name = name
                break
        return self._generate_mock_epg(ch_name, service_ref, 24)

    async def search_epg(self, query: str) -> list[EPGEvent]:
        all_events = []
        for ch_name, ch_ref, _, _ in self._all_channels[:10]:
            events = self._generate_mock_epg(ch_name, ch_ref, 5)
            all_events.extend(events)
        return [e for e in all_events if query.lower() in e.title.lower()]

    # ──── Volume ────

    async def get_volume(self) -> VolumeState:
        return VolumeState(volume=self._volume, is_muted=self._muted)

    async def set_volume(self, action: str, value: Optional[int] = None) -> VolumeState:
        if action == "up":
            self._volume = min(100, self._volume + 5)
        elif action == "down":
            self._volume = max(0, self._volume - 5)
        elif action == "mute":
            self._muted = not self._muted
        elif action == "set" and value is not None:
            self._volume = max(0, min(100, value))
        return await self.get_volume()

    # ──── Timers ────

    async def get_timers(self) -> list[Timer]:
        return [Timer(
            id=t["id"],
            service_ref=t["service_ref"],
            channel_name=t["channel_name"],
            begin_time=t["begin_time"],
            end_time=t["end_time"],
            name=t["name"],
            description=t["description"],
            state=t["state"],
            repeated=t["repeated"],
            repeated_days=t["repeated_days"],
        ) for t in self._timers]

    async def add_timer(self, timer: Timer) -> TimerResponse:
        new_timer = timer.model_dump()
        new_timer["id"] = self._timer_id_counter
        self._timer_id_counter += 1
        self._timers.append(new_timer)
        log.info("mock_timer_added", name=timer.name)
        return TimerResponse(result=True, message=f"Timer '{timer.name}' created")

    async def delete_timer(self, service_ref: str, begin_time: str, end_time: str) -> TimerResponse:
        initial_count = len(self._timers)
        self._timers = [t for t in self._timers if not (
            t["service_ref"] == service_ref and
            t["begin_time"] == begin_time and
            t["end_time"] == end_time
        )]
        if len(self._timers) < initial_count:
            return TimerResponse(result=True, message="Timer deleted")
        return TimerResponse(result=False, message="Timer not found")

    # ──── Power ────

    async def set_power_state(self, action: str) -> bool:
        if action in ("toggle", "standby"):
            self._standby = not self._standby
        elif action == "wakeup":
            self._standby = False
        elif action in ("reboot", "deep_standby"):
            self._standby = True
        log.info("mock_power", action=action, standby=self._standby)
        return True

    # ──── Stream ────

    async def get_stream_url(self, service_ref: str) -> Optional[str]:
        return f"http://{self.host}:8001/{service_ref}"

    # ──── Discovery ────

    @staticmethod
    async def discover(network: str = "192.168.1.0/24") -> list[DiscoveredDevice]:
        return [
            DiscoveredDevice(
                host="127.0.0.1",
                port=0,
                name="Mock STB (Demo)",
                device_type="mock",
                model="MockBox 4K Ultra",
            )
        ]
