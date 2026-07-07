"""
PrusaLink API client.
Docs: https://github.com/prusa3d/Prusa-Link-Web/blob/master/spec/openapi.yaml

PrusaLink runs on each Pi and exposes a REST API per printer.
This client wraps all interactions.
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import httpx

from core.config import settings


@dataclass
class PrinterConfig:
    printer_id: str
    name: str
    pi_id: str
    base_url: str      # e.g. http://192.168.1.101:8080
    api_key: str
    allowed_user_groups: List[str] = field(default_factory=lambda: ["all"])


@dataclass
class PrinterStatus:
    printer_id: str
    name: str
    state: str          # idle | printing | paused | error | offline | maintenance
    state_text: str
    progress_pct: float
    job_name: Optional[str]
    filament: Optional[str]
    nozzle_temp: Optional[float]
    bed_temp: Optional[float]
    time_remaining_sec: Optional[int]
    camera_url: Optional[str]
    version: Optional[str]
    pi_id: str


def _build_printer_configs() -> Dict[str, PrinterConfig]:
    """Parse PRUSALINK_CONFIG from settings into PrinterConfig objects."""
    configs = {}
    for pi in settings.prusalink_instances:
        pi_id = pi["pi_id"]
        host = pi["host"]
        for p in pi["printers"]:
            port = p["port"]
            base_url = f"{host}:{port}"
            configs[p["printer_id"]] = PrinterConfig(
                printer_id=p["printer_id"],
                name=p["name"],
                pi_id=pi_id,
                base_url=base_url,
                api_key=p["api_key"],
                allowed_user_groups=p.get("allowed_user_groups", ["all"]),
            )
    return configs


PRINTER_CONFIGS: Dict[str, PrinterConfig] = _build_printer_configs()


class PrusaLinkClient:
    """Async HTTP client for a single PrusaLink instance."""

    def __init__(self, config: PrinterConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"X-Api-Key": config.api_key},
            timeout=10.0,
        )

    async def get_printer_status(self) -> Dict[str, Any]:
        """GET /api/printer — printer state, temps."""
        try:
            r = await self._client.get("/api/printer")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_job(self) -> Dict[str, Any]:
        """GET /api/job — current job info."""
        try:
            r = await self._client.get("/api/job")
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    async def get_version(self) -> str:
        """GET /api/version — firmware version."""
        try:
            r = await self._client.get("/api/version")
            r.raise_for_status()
            data = r.json()
            return data.get("text", "unknown")
        except Exception:
            return "unknown"

    async def upload_and_print(self, filename: str, gcode_bytes: bytes) -> Dict[str, Any]:
        """
        POST /api/files/local — upload gcode file.
        Then POST /api/job with command=start to print it.
        """
        try:
            # Upload file
            files = {"file": (filename, gcode_bytes, "text/x.gcode")}
            r = await self._client.post(
                "/api/files/local",
                files=files,
                data={"print": "false"},  # Upload only, start separately
            )
            r.raise_for_status()

            # Select and start the file
            r2 = await self._client.post(
                f"/api/files/local/{filename}",
                json={"command": "select", "print": True},
            )
            r2.raise_for_status()
            return {"success": True, "filename": filename}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def pause_job(self) -> bool:
        try:
            r = await self._client.post("/api/job", json={"command": "pause", "action": "pause"})
            return r.status_code == 204
        except Exception:
            return False

    async def resume_job(self) -> bool:
        try:
            r = await self._client.post("/api/job", json={"command": "pause", "action": "resume"})
            return r.status_code == 204
        except Exception:
            return False

    async def cancel_job(self) -> bool:
        try:
            r = await self._client.post("/api/job", json={"command": "cancel"})
            return r.status_code == 204
        except Exception:
            return False

    async def is_idle(self) -> bool:
        status = await self.get_printer_status()
        if "error" in status:
            return False
        state = status.get("state", {}).get("text", "").lower()
        return state in ("operational", "idle", "ready")

    async def close(self):
        await self._client.aclose()


# Singleton clients per printer
_clients: Dict[str, PrusaLinkClient] = {}


def get_client(printer_id: str) -> Optional[PrusaLinkClient]:
    if printer_id not in PRINTER_CONFIGS:
        return None
    if printer_id not in _clients:
        _clients[printer_id] = PrusaLinkClient(PRINTER_CONFIGS[printer_id])
    return _clients[printer_id]


async def fetch_all_statuses() -> List[PrinterStatus]:
    """Poll all printers concurrently and return their status."""
    async def fetch_one(printer_id: str, cfg: PrinterConfig) -> PrinterStatus:
        client = get_client(printer_id)
        
        raw_status = await client.get_printer_status()
        raw_job = await client.get_job()
        
        if "error" in raw_status:
            return PrinterStatus(
                printer_id=printer_id,
                name=cfg.name,
                state="offline",
                state_text="Offline",
                progress_pct=0.0,
                job_name=None,
                filament=None,
                nozzle_temp=None,
                bed_temp=None,
                time_remaining_sec=None,
                camera_url=None,
                version=None,
                pi_id=cfg.pi_id,
            )

        state_obj = raw_status.get("state", {})
        state_text = state_obj.get("text", "Unknown")
        state = _normalize_state(state_text)

        temps = raw_status.get("temperature", {})
        nozzle = temps.get("tool0", {}).get("actual")
        bed = temps.get("bed", {}).get("actual")

        job_data = raw_job.get("job", {})
        file_data = job_data.get("file", {})
        job_name = file_data.get("name")

        progress = raw_job.get("progress", {})
        pct = progress.get("completion", 0.0) or 0.0
        time_left = progress.get("printTimeLeft")

        # Camera URL — PrusaLink exposes a snapshot endpoint
        camera_url = f"{cfg.base_url}/api/webcam?action=snapshot"

        return PrinterStatus(
            printer_id=printer_id,
            name=cfg.name,
            state=state,
            state_text=state_text,
            progress_pct=round(pct * 100, 1) if pct <= 1 else round(pct, 1),
            job_name=job_name,
            filament=raw_status.get("material"),
            nozzle_temp=nozzle,
            bed_temp=bed,
            time_remaining_sec=time_left,
            camera_url=camera_url,
            version=None,
            pi_id=cfg.pi_id,
        )

    tasks = [fetch_one(pid, cfg) for pid, cfg in PRINTER_CONFIGS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    statuses = []
    for pid, result in zip(PRINTER_CONFIGS.keys(), results):
        if isinstance(result, Exception):
            cfg = PRINTER_CONFIGS[pid]
            statuses.append(PrinterStatus(
                printer_id=pid, name=cfg.name, state="offline", state_text="Error",
                progress_pct=0, job_name=None, filament=None, nozzle_temp=None,
                bed_temp=None, time_remaining_sec=None, camera_url=None,
                version=None, pi_id=cfg.pi_id,
            ))
        else:
            statuses.append(result)
    return statuses


def _normalize_state(state_text: str) -> str:
    s = state_text.lower()
    if any(x in s for x in ("printing", "busy", "resuming")):
        return "printing"
    if any(x in s for x in ("pause", "paused")):
        return "paused"
    if any(x in s for x in ("error", "stopped")):
        return "error"
    if any(x in s for x in ("offline", "disconnect")):
        return "offline"
    if "maintenance" in s:
        return "maintenance"
    return "idle"


def get_all_printer_configs() -> Dict[str, PrinterConfig]:
    return PRINTER_CONFIGS