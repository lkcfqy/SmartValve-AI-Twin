"""SmartValve AI Twin public package and release identifiers."""

__version__ = "0.4.0"
MODEL_VERSION = "valvedna-rules-0.3.0"

from smartvalve.pipeline import TwinRun, run_from_frames, run_twin  # noqa: E402

__all__ = ["MODEL_VERSION", "TwinRun", "run_from_frames", "run_twin"]
