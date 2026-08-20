#!/usr/bin/env python3
"""In metric test ra terminal."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import MODEL_BUNDLE_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.model.evaluate import evaluate_model

parser = argparse.ArgumentParser(description="Đánh giá Isolation Forest")
parser.add_argument("--data", type=Path, default=SAMPLE_LOGS_PATH)
parser.add_argument("--model", type=Path, default=MODEL_BUNDLE_PATH)
args = parser.parse_args()
print(json.dumps(evaluate_model(args.data, args.model), ensure_ascii=False, indent=2))
