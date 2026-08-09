#!/usr/bin/env python3
"""CLI chạy EDA và xuất biểu đồ."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import EDA_FIGURES_DIR, SAMPLE_LOGS_PATH, ensure_directories
from qos_anomaly.data.features import FeatureBuilder
from qos_anomaly.data.loader import load_logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Khám phá dữ liệu log QoS")
    parser.add_argument("--data", type=Path, default=SAMPLE_LOGS_PATH)
    parser.add_argument("--out", type=Path, default=EDA_FIGURES_DIR)
    args = parser.parse_args()

    ensure_directories()
    args.out.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    df = load_logs(args.data, require_labels=True)
    fb = FeatureBuilder()
    features = fb.fit_transform(df)

    # 1. Latency distribution
    plt.figure(figsize=(8, 5))
    sns.histplot(df["response_time_ms"], bins=50, kde=True)
    plt.title("Phân bố Response Time (ms)")
    plt.xlabel("response_time_ms")
    plt.tight_layout()
    plt.savefig(args.out / "01_latency_distribution.png", dpi=120)
    plt.close()

    # 2. Status code
    plt.figure(figsize=(8, 5))
    sns.countplot(data=df, x="status_code", order=sorted(df["status_code"].unique()))
    plt.title("Phân bố Status Code")
    plt.tight_layout()
    plt.savefig(args.out / "02_status_code.png", dpi=120)
    plt.close()

    # 3. Request rate
    plt.figure(figsize=(8, 5))
    sns.histplot(features["request_rate"], bins=40, kde=True)
    plt.title("Phân bố Request Rate (theo IP)")
    plt.tight_layout()
    plt.savefig(args.out / "03_request_rate.png", dpi=120)
    plt.close()

    # 4. Anomaly type
    if "anomaly_type" in df.columns:
        plt.figure(figsize=(8, 5))
        sns.countplot(data=df, x="anomaly_type")
        plt.title("Phân bố loại Anomaly")
        plt.xticks(rotation=30)
        plt.tight_layout()
        plt.savefig(args.out / "04_anomaly_type.png", dpi=120)
        plt.close()

    # 5. Feature correlation
    plt.figure(figsize=(10, 8))
    corr = features.corr()
    sns.heatmap(corr, cmap="coolwarm", center=0, square=True)
    plt.title("Ma trận tương quan Features")
    plt.tight_layout()
    plt.savefig(args.out / "05_feature_correlation.png", dpi=120)
    plt.close()

    print(f"Đã lưu 5 biểu đồ EDA vào {args.out}")


if __name__ == "__main__":
    main()
