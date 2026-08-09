#!/usr/bin/env python3
"""CLI sinh dataset log mẫu."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import RANDOM_STATE, SAMPLE_LOGS_JSON_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.data.generator import generate_logs, save_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh dataset log QoS offline")
    parser.add_argument("--n-rows", type=int, default=1000)
    parser.add_argument("--anomaly-ratio", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=RANDOM_STATE)
    parser.add_argument("--output-csv", type=Path, default=SAMPLE_LOGS_PATH)
    parser.add_argument("--output-json", type=Path, default=SAMPLE_LOGS_JSON_PATH)
    args = parser.parse_args()

    df = generate_logs(n_rows=args.n_rows, anomaly_ratio=args.anomaly_ratio, seed=args.seed)
    csv_path, json_path = save_dataset(df, args.output_csv, args.output_json)
    anomaly_pct = df["is_anomaly"].mean() * 100
    print(f"Đã tạo {len(df)} bản ghi | anomaly={anomaly_pct:.2f}%")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
