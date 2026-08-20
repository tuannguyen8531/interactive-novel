"""Print the current provider-real quality benchmark report."""

from __future__ import annotations

import json

from src.config import get_settings
from src.paths import get_runtime_paths
from src.services.quality import benchmark_telemetry


def main() -> int:
    paths = get_runtime_paths(get_settings().runtime_dir)
    report = benchmark_telemetry(paths.telemetry)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    if report.sample_count == 0:
        print("No provider-real samples. Set TELEMETRY_ENABLED=true and play turns before benchmarking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
