#!/usr/bin/env python3
"""CLI đánh giá mô hình."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import EVAL_REPORT_PATH, MODEL_BUNDLE_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.model.evaluate import evaluate_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá mô hình anomaly detection")
    parser.add_argument("--data", type=Path, default=SAMPLE_LOGS_PATH)
    parser.add_argument("--model", type=Path, default=MODEL_BUNDLE_PATH)
    parser.add_argument("--out", type=Path, default=EVAL_REPORT_PATH)
    args = parser.parse_args()

    report = evaluate_model(args.data, args.model, args.out)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
