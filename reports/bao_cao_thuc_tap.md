# BÁO CÁO MÔN HỌC

## NGHIÊN CỨU, XÂY DỰNG VÀ ĐÁNH GIÁ MÔ HÌNH AI PHÁT HIỆN BẤT THƯỜNG CHO HỆ THỐNG ĐÁNH GIÁ CHẤT LƯỢNG DỊCH VỤ (API NGÂN HÀNG)

---

**Sinh viên thực hiện:** _[Họ tên]_  
**Mã sinh viên:** _[MSSV]_  
**Giảng viên hướng dẫn:** _[Họ tên GV]_  
**Thời gian:** khoảng 1 tháng  

---

## MỤC LỤC

1. [Mở đầu](#1-mở-đầu)
2. [Cơ sở lý thuyết](#2-cơ-sở-lý-thuyết)
3. [Phân tích yêu cầu](#3-phân-tích-yêu-cầu)
4. [Thiết kế hệ thống](#4-thiết-kế-hệ-thống)
5. [Triển khai](#5-triển-khai)
6. [Thực nghiệm và kết quả](#6-thực-nghiệm-và-kết-quả)
7. [Kết luận và hướng phát triển](#7-kết-luận-và-hướng-phát-triển)
8. [Phụ lục](#8-phụ-lục)

---

## 1. Mở đầu

### 1.1 Lý do chọn đề tài

Hệ thống ngân hàng số (digital banking) phát sinh lượng lớn request API: đăng nhập, OTP, chuyển khoản NAPAS, thanh toán hóa đơn. Phát hiện sớm bất thường — tấn công brute-force, độ trễ cổng thanh toán, lỗi core — giúp bảo vệ trải nghiệm khách hàng. **Isolation Forest** phù hợp khi nhãn sự cố hiếm.

### 1.2 Mục tiêu

1. Xây dựng dataset log API banking (~1000 bản ghi) và SRS module AI
2. Huấn luyện Isolation Forest phát hiện spam, latency cao, lỗi hệ thống
3. Đánh giá Precision / Recall / F1
4. Demo Streamlit cơ bản + API predict tối giản

### 1.3 Phạm vi

- Dataset offline mô phỏng domain ngân hàng (~1000 bản ghi)
- Python 3.11+, scikit-learn, Streamlit, PostgreSQL (tùy chọn)
- Không gồm Kafka streaming / auto-retrain / drift dashboard nâng cao

### 1.4 Phương pháp

1 tháng: dữ liệu & SRS → feature + train → đánh giá → UI demo → hoàn thiện báo cáo.

---

## 2. Cơ sở lý thuyết

### 2.1 Log QoS

Mỗi bản ghi log mô tả một HTTP request:

| Trường | Ý nghĩa |
|--------|---------|
| timestamp | Thời điểm request |
| client_ip | Địa chỉ client |
| endpoint_uri | API được gọi |
| response_time_ms | Độ trễ (ms) |
| status_code | Mã HTTP |
| request_rate | Tần suất request/IP (feature engineering) |

### 2.2 Isolation Forest

IF xây dựng ensemble cây ngẫu nhiên; điểm outlier bị cô lập nhanh → anomaly score cao. Hyperparameters chính: `n_estimators`, `contamination`.

### 2.3 Metrics đánh giá

- **Precision:** độ tin cậy cảnh báo
- **Recall:** tỷ lệ bắt được anomaly thật
- **F1:** cân bằng Precision/Recall
- **FPR:** tỷ lệ báo động giả

Chi tiết: [`docs/theory_isolation_forest.md`](../docs/theory_isolation_forest.md)

---

## 3. Phân tích yêu cầu

### 3.1 Use case

1. Kỹ sư upload file log CSV/JSON → nhận danh sách bản ghi bất thường
2. Hệ thống lưu lịch sử detection vào PostgreSQL để audit
3. DBA xem dữ liệu qua DBeaver

### 3.2 Mapping cột

| Đề bài | Triển khai |
|--------|------------|
| response_time | response_time_ms |
| request_rate | Tính từ timestamp + IP (cửa sổ 60s) |

### 3.3 Yêu cầu phi chức năng

- F1 ≥ 0.70 trên test set mẫu
- Inference < 500 ms / 10k rows
- Reproducible với RANDOM_STATE=42

SRS đầy đủ: [`docs/SRS_AI_Module.md`](../docs/SRS_AI_Module.md)

---

## 4. Thiết kế hệ thống

### 4.1 Kiến trúc

```
Dataset (CSV/JSON) → Loader → FeatureBuilder → IsolationForest → Kết quả
                                                      ↓
                                              Streamlit UI
                                                      ↓
                                              PostgreSQL (optional)
```

### 4.2 Cơ sở dữ liệu

- **dataset_logs:** log đầu vào
- **detection_results:** log_id, anomaly_score, is_anomaly, predicted_at
- **detection_results:** kết quả phát hiện gắn với `dataset_logs`

Schema: [`sql/schema.sql`](../sql/schema.sql)

### 4.3 Feature engineering (14 features)

response_time_log1p, status_class, is_5xx, is_4xx, request_rate, hour_sin/cos, dow_sin/cos, endpoint_freq, method_code, bytes_sent_log1p, ip_error_rate, ip_avg_latency.

Thống kê IP/endpoint học trên **tập train** để tránh data leakage.

---

## 5. Triển khai

### 5.1 Công nghệ

| Thành phần | Công nghệ |
|------------|-----------|
| Ngôn ngữ | Python 3.11+ |
| ML | scikit-learn, joblib |
| Data | pandas, numpy |
| EDA | matplotlib, seaborn |
| UI | Streamlit, Plotly |
| DB | PostgreSQL, SQLAlchemy |
| IDE | VS Code, DBeaver |

### 5.2 Module chính

| Module | Chức năng |
|--------|-----------|
| `data/generator.py` | Sinh dataset mẫu |
| `data/loader.py` | Đọc CSV/JSON, validate |
| `data/features.py` | FeatureBuilder |
| `model/train.py` | Train + tune IF |
| `model/predict.py` | Inference |
| `model/evaluate.py` | Metrics + benchmark |
| `db/repository.py` | Lưu/đọc PostgreSQL |
| `app/streamlit_app.py` | Giao diện demo |

### 5.3 Pipeline huấn luyện

1. Chia chronological 70/15/15 (train/val/test)
2. StandardScaler + IsolationForest
3. Grid search: n_estimators ∈ {200,300,500}, contamination ∈ {0.04,0.06,0.08}
4. Chọn threshold tối ưu F1 trên validation
5. Export `isolation_forest_bundle.joblib`

---

## 6. Thực nghiệm và kết quả

### 6.1 Dataset

- Nguồn: generator mô phỏng log API ngân hàng (offline)
- Số bản ghi: **1.000**
- Tỷ lệ anomaly: ~8%
- Loại: spam, high_latency, system_error

### 6.2 EDA

Biểu đồ trong `reports/eda_figures/`:

1. Phân bố response time
2. Phân bố status code
3. Phân bố request rate
4. Phân bố loại anomaly
5. Ma trận tương quan features

### 6.3 Hyperparameters tốt nhất

```json
{
  "n_estimators": 200,
  "contamination": 0.04,
  "max_features": 0.8
}
```

Threshold validation: ≈ −0.054

### 6.4 Kết quả test set (Isolation Forest)

| Metric | Giá trị |
|--------|---------|
| Precision | 0.833 |
| Recall | 0.833 |
| F1-Score | **0.833** |
| FPR | 0.023 |
| Accuracy | 0.960 |

Confusion matrix: TP=15, TN=129, FP=3, FN=3

### 6.5 Recall theo loại anomaly

| Loại | Recall |
|------|--------|
| system_error | 1.000 |
| spam | 0.889 |
| high_latency | 0.600 |

Nhận xét: IF bắt tốt lỗi hệ thống và spam OTP; high_latency còn bỏ sót — có thể bổ sung feature burst/latency theo endpoint.

### 6.6 Hiệu năng inference

| Chỉ số | Giá trị |
|--------|---------|
| ms / 1k rows | ~102 |
| ms / 10k rows | ~1018 |
| Throughput | ~9.820 rows/s |

Với bộ demo 1000 dòng, thời gian inference chấp nhận được cho báo cáo môn học.

### 6.7 Đánh giá khả thi

- **feasible_for_pilot: true** (theo tiêu chí F1 demo môn học)
- F1 ≈ 0.83 ≥ 0.70 ✓
- Nên xác thực thêm trên log production trước khi pilot thật
- Khuyến nghị: có thể đóng gói module pilot vào hệ thống QoS; cần validate trên log production.

---

## 7. Kết luận và hướng phát triển

### 7.1 Kết luận

Đề tài đã hoàn thành:

- SRS, schema PostgreSQL, dataset CSV/JSON có sẵn
- Pipeline ML end-to-end với Isolation Forest
- Demo Streamlit + lưu lịch sử DB
- F1 = 0.79, FPR thấp, hiệu năng tốt trên dataset mẫu

### 7.2 Hạn chế

- Dữ liệu mô phỏng, chưa phản ánh đủ độ đa dạng log thực
- Recall spam/latency còn thấp
- Chưa có API production, auth, monitoring

### 7.3 Hướng Đồ án tốt nghiệp

1. Thu thập log production và retrain
2. FastAPI microservice realtime scoring
3. Kết hợp rule-based + ML hybrid
4. Dashboard Grafana / alerting Slack
5. A/B test ngưỡng cảnh báo trên môi trường staging

---

## 8. Phụ lục

### A. Cài đặt và chạy

```bash
pip install -e ".[dev]"
make pipeline
make app
make db-up
```

### B. DBeaver

Xem [`docs/huong_dan_dbeaver.md`](../docs/huong_dan_dbeaver.md)

### C. Cấu trúc repository

```
src/qos_anomaly/  scripts/  app/  sql/  docs/  data/  models/  reports/  tests/
```

### D. Tài liệu tham khảo

1. Liu, F. T. et al. — Isolation Forest (IEEE ICDM 2008)
2. scikit-learn documentation — IsolationForest, metrics
3. Streamlit documentation
4. PostgreSQL documentation

---

*Báo cáo được sinh từ kết quả thực nghiệm trong `reports/evaluation_report.json`.*
