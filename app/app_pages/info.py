"""Trang thông tin mô hình và đánh giá."""
from __future__ import annotations

import bootstrap  # noqa: F401

import streamlit as st

from qos_anomaly.config import get_settings
from runtime import get_service
from ui import section_box

settings = get_settings()
service = get_service()

ready, message = service.check_model_ready()
if not ready:
    st.error(message, icon=":material/error:")
    st.stop()

info = service.get_model_info()

with section_box("Mô hình đang dùng", icon=":material/model_training:"):
    st.badge(
        info.get("display_name") or "Model",
        icon=":material/verified:",
        color="blue",
    )
    st.caption(f"`{info.get('model_id', '—')}` · {settings.app_env}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Ngưỡng", f"{info['threshold']:.4f}")
    val_f1 = info.get("metrics_val", {}).get("f1")
    test_f1 = info.get("metrics_test_preview", {}).get("f1")
    if val_f1 is not None:
        c2.metric("F1 kiểm chứng", f"{val_f1:.3f}")
    if test_f1 is not None:
        c3.metric("F1 kiểm tra", f"{test_f1:.3f}")

    params = info.get("best_params") or {}
    if params:
        with st.expander("Tham số Isolation Forest", icon=":material/tune:"):
            st.json(params)

eval_summary = service.get_eval_summary()
with section_box(
    "Đánh giá",
    icon=":material/assessment:",
    help_text=(
        "Precision: trong số cảnh báo, bao nhiêu đúng. "
        "Recall: bắt được bao nhiêu anomaly thật. "
        "F1: cân bằng Precision/Recall. "
        "FPR: tỷ lệ báo nhầm trên mẫu bình thường."
    ),
    tip_key="tip_eval_metrics",
):
    if eval_summary:
        metrics = eval_summary.get("metrics", {})
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Precision", f"{metrics.get('precision', 0):.3f}")
        m2.metric("Recall", f"{metrics.get('recall', 0):.3f}")
        m3.metric("F1", f"{metrics.get('f1', 0):.3f}")
        m4.metric("FPR", f"{metrics.get('fpr', 0):.4f}")
        feas = eval_summary.get("feasibility", {})
        if feas.get("pilot_recommendation"):
            st.caption(feas["pilot_recommendation"])
    else:
        st.caption("Chưa có báo cáo · `python3 scripts/evaluate_model.py`")

with section_box("Cơ sở dữ liệu", icon=":material/database:"):
    if service.check_db():
        st.badge("Đã kết nối", icon=":material/check:", color="green")
    else:
        st.badge("Chưa kết nối", icon=":material/link_off:", color="gray")
        st.caption("Tùy chọn · `docker compose up -d`")
