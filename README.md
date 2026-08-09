# AI Phát hiện Bất thường QoS — API ngân hàng

Báo cáo môn học PTIT: module **Isolation Forest** phát hiện bất thường trên log API ngân hàng (spam/OTP, latency cao, lỗi hệ thống).

## Phạm vi (1 tháng — bản rút gọn)

- Dataset ~1000 bản ghi mô phỏng log digital banking
- Feature engineering + train/eval Isolation Forest
- Demo Streamlit: Phát hiện · Trực quan · Lịch sử DB (tùy chọn) · Thông tin
- API FastAPI tối giản: health + predict
- PostgreSQL lưu lịch sử (tùy chọn)

## Cài đặt

```bash
cd ai-anomaly-detection-qos
python3 -m pip install -e ".[dev]"
cp .env.example .env
```

## Chạy nhanh (demo)

```bash
# Đã có sẵn data/raw/train_logs_1000.csv và model QoS Forest 1.0
cd app && python3 -m streamlit run streamlit_app.py
```

Trong app: bấm **Dùng bộ mẫu 1000 dòng** → **Chạy phát hiện** → xem **Trực quan**.

Train / đánh giá lại (khi đổi dataset):

```bash
python3 scripts/generate_dataset.py --n-rows 1000
python3 scripts/train_model.py --data data/raw/train_logs_1000.csv
python3 scripts/evaluate_model.py --data data/raw/train_logs_1000.csv
```

API (tùy chọn):

```bash
python3 -m uvicorn qos_anomaly.api.app:app --host 0.0.0.0 --port 8000 --reload
# Docs: http://localhost:8000/docs
```

Hoặc dùng `make data train eval app api test`.

## Dataset

| File | Mô tả |
|------|--------|
| `data/raw/train_logs_1000.csv` | Bộ train/demo chính |
| `data/raw/train_logs_1000.json` | Cùng nội dung (upload JSON) |
| `data/raw/train_real_template.csv` | Template nếu có log thật |

Endpoint mẫu: `/api/v1/auth/login`, `/api/v1/transfers/napas`, `/api/v1/payments/bill`, …

Hướng dẫn: [`docs/huong_dan_dataset_thuc_te.md`](docs/huong_dan_dataset_thuc_te.md)

## Cấu trúc

```
src/qos_anomaly/   # data, model, services, api, db, viz
app/               # Streamlit (detect, visualize, history, info)
scripts/           # generate / train / eval / eda
docs/              # SRS, lý thuyết, dataset
tests/             # pytest
```

## PostgreSQL (tùy chọn)

```bash
docker compose up -d
```

Bật **Lưu kết quả vào PostgreSQL** ở sidebar Streamlit khi chạy phát hiện.

## Tài liệu

- [`docs/SRS_AI_Module.md`](docs/SRS_AI_Module.md)
- [`docs/theory_isolation_forest.md`](docs/theory_isolation_forest.md)
- [`reports/bao_cao_thuc_tap.md`](reports/bao_cao_thuc_tap.md)
# demo-bank-logs
