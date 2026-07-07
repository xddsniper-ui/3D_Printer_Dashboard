"""
Central configuration — edit this file to configure your printer farm.
All PrusaLink API keys and Pi addresses go here.
"""

from pydantic_settings import BaseSettings
from typing import List, Dict, Any
import json
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PrintFarm"
    SECRET_KEY: str = "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET-IN-PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    ALGORITHM: str = "HS256"

    # Database (SQLite for simplicity, swap for PostgreSQL in prod)
    DATABASE_URL: str = "sqlite+aiosqlite:///./printfarm.db"

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8000", "http://localhost:3000", "https://id-preview--8fdb677c-37e4-47cf-8fb6-ef65a7eb2e63.lovable.app"]

    # PrusaLink instances — one entry per Pi
    # Each Pi manages 2 printers. PrusaLink exposes them on different ports or paths.
    # Format: { "pi_id": { "host": "...", "printers": [...] } }
    PRUSALINK_CONFIG: str = json.dumps([
        {
            "pi_id": "pi-01",
            "host": "http://192.168.1.101",
            "printers": [
                {
                    "printer_id": "printer-01",
                    "name": "Prusa MK4 #1",
                    "port": 8080,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],  # "all" or list of group names
                },
                {
                    "printer_id": "printer-02",
                    "name": "Prusa MK4 #2",
                    "port": 8081,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
            ],
        },
        {
            "pi_id": "pi-02",
            "host": "http://192.168.1.102",
            "printers": [
                {
                    "printer_id": "printer-03",
                    "name": "Prusa MK4 #3",
                    "port": 8080,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
                {
                    "printer_id": "printer-04",
                    "name": "Prusa MK4 #4",
                    "port": 8081,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
            ],
        },
        {
            "pi_id": "pi-03",
            "host": "http://192.168.1.103",
            "printers": [
                {
                    "printer_id": "printer-05",
                    "name": "Prusa MK4 #5",
                    "port": 8080,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
                {
                    "printer_id": "printer-06",
                    "name": "Prusa MK4 #6",
                    "port": 8081,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
            ],
        },
        {
            "pi_id": "pi-04",
            "host": "http://192.168.1.104",
            "printers": [
                {
                    "printer_id": "printer-07",
                    "name": "Prusa MK4 #7",
                    "port": 8080,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
                {
                    "printer_id": "printer-08",
                    "name": "Prusa MK4 #8",
                    "port": 8081,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
            ],
        },
        {
            "pi_id": "pi-05",
            "host": "http://192.168.1.105",
            "printers": [
                {
                    "printer_id": "printer-09",
                    "name": "Prusa MK4 #9",
                    "port": 8080,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
                {
                    "printer_id": "printer-10",
                    "name": "Prusa MK4 #10",
                    "port": 8081,
                    "api_key": "YOUR_PRUSALINK_API_KEY_HERE",
                    "allowed_user_groups": ["all"],
                },
            ],
        },
    ])

    # Queue settings
    QUEUE_POLL_INTERVAL_SECONDS: int = 10  # How often to check if a printer is free
    MAX_QUEUE_PER_PRINTER: int = 20

    # Upload settings
    MAX_GCODE_SIZE_MB: int = 500
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"

    @property
    def prusalink_instances(self) -> List[Dict[str, Any]]:
        return json.loads(self.PRUSALINK_CONFIG)


settings = Settings()
