#!/usr/bin/env python3
"""CLI huấn luyện Isolation Forest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import MODEL_BUNDLE_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.model.train import train_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Huấn luyện Isolation Forest")
    parser.add_argument("--data", type=Path, default=SAMPLE_LOGS_PATH)
    parser.add_argument("--out", type=Path, default=MODEL_BUNDLE_PATH)
    args = parser.parse_args()

    result = train_pipeline(args.data, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
