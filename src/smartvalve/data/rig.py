"""Adapter for the future CNY 200 desktop rig and enterprise CSV exports."""

from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd

from smartvalve.data.contract import DataQualityReport, validate_valve_frame


def load_canonical_csv(
    source: str | Path | bytes | BinaryIO | TextIO,
) -> tuple[pd.DataFrame, DataQualityReport]:
    if isinstance(source, bytes):
        handle: str | Path | BinaryIO | TextIO = BytesIO(source)
    elif isinstance(source, str) and "\n" in source:
        handle = StringIO(source)
    else:
        handle = source
    frame = pd.read_csv(handle)
    report = validate_valve_frame(frame, strict=True)
    return frame, report
