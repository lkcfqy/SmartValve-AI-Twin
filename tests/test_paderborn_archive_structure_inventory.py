from __future__ import annotations

import json
import runpy
from pathlib import Path

_SCRIPT = runpy.run_path(
    str(
        Path(__file__).parents[1]
        / "scripts"
        / "paderborn_archive_structure_inventory.py"
    )
)
structure_signature = _SCRIPT["structure_signature"]
summarize_signatures = _SCRIPT["summarize_signatures"]


def _structure(samples: int, dtype: str = "float64") -> dict[str, object]:
    return {
        "channels": {
            channel: {"shape": [samples], "dtype": dtype, "samples": samples}
            for channel in ("vibration", "current_u", "current_v")
        }
    }


def test_structure_signature_is_order_stable_and_summary_counts() -> None:
    first = _structure(256001)
    reordered = {"channels": dict(reversed(list(first["channels"].items())))}
    other = _structure(256000)

    first_signature = structure_signature(first)
    assert first_signature == structure_signature(reordered)
    assert json.loads(first_signature)[0]["channel"] == "current_u"

    summary = summarize_signatures(
        [
            {"structure_status": "parsed", "structure_signature": first_signature},
            {
                "structure_status": "parsed",
                "structure_signature": structure_signature(reordered),
            },
            {
                "structure_status": "parsed",
                "structure_signature": structure_signature(other),
            },
            {"structure_status": "parse_failed", "error_type": "TypeError"},
        ]
    )
    assert sorted(row["measurement_count"] for row in summary) == [1, 2]
