"""Small local utilities shared by notebooks."""

from pathlib import Path
from typing import Iterable

from .config import SETTINGS, Settings


def ensure_output_directories(settings: Settings = SETTINGS) -> None:
    """Create cache and output directories if they do not exist."""
    paths: Iterable[Path] = (
        settings.data_raw,
        settings.data_processed,
        settings.output_maps,
        settings.output_charts,
        settings.output_tables,
        settings.output_qa,
    )
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
