# Đặc tả yêu cầu (SRS) — Module AI Phát hiện Bất thường QoS (ngân hàng)

**Phiên bản:** 2.0 (rút gọn báo cáo môn học)  
**Phạm vi thời gian:** ~1 tháng  

---

## 1. Mục đích

Xây dựng module AI phát hiện bất thường từ log API dịch vụ ngân hàng số (digital banking / payment gateway), phục vụ báo cáo môn học.

## 2. Phạm vi

**Trong phạm vi**
- Dataset offline ~1000 bản ghi (mô phỏng log banking)
- Feature engineering + Isolation Forest
- UI Streamlit: upload / nhập tay / biểu đồ / lịch sử DB tùy chọn
- API predict tối giản (FastAPI)
- Đánh giá P/R/F1

**Ngoài phạm vi (đã cắt)**
- Kafka streaming, auto-retrain, drift dashboard nâng cao

## 3. Schema dữ liệu

| Trường | Kiểu | Ghi chú |
|--------|------|---------|
| timestamp | datetime | ISO8601 |
| client_ip | string | IP client / NAT |
| endpoint_uri | string | vd `/api/v1/transfers/napas` |
| http_method | string | GET/POST/... |
| response_time_ms | float | latency (ms) |
| status_code | int | HTTP status |
| bytes_sent | int | kích thước response |
| is_anomaly | 0/1 | nhãn đánh giá |
| anomaly_type | string | normal / spam / high_latency / system_error |

## 4. Yêu cầu chức năng

- FR-01 Nạp CSV/JSON đúng schema
- FR-02 Feature engineering (rate theo IP, cyclic time, status, …)
- FR-03 Phát hiện bằng Isolation Forest + ngưỡng
- FR-04 Hiển thị bảng + biểu đồ Streamlit
- FR-05 Lưu lịch sử PostgreSQL (tùy chọn)

## 5. Tiêu chí chấp nhận

- [ ] Train trên `train_logs_1000.csv` thành công
- [ ] Upload file và nhận kết quả anomaly
- [ ] Có `evaluation_report.json`
- [ ] Demo Streamlit chạy được
- [ ] pytest pass
