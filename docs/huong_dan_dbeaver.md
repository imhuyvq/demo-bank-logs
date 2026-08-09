# Hướng dẫn kết nối PostgreSQL bằng DBeaver

## 1. Khởi động database

```bash
cd ai-anomaly-detection-qos
docker compose up -d
```

Chờ container `qos_anomaly_db` healthy. Schema tự chạy từ `sql/schema.sql` khi container khởi tạo lần đầu.

Nếu cần tạo bảng thủ công:

```bash
python3 -c "from qos_anomaly.db import init_db; init_db()"
```

## 2. Cài DBeaver

- Tải tại: https://dbeaver.io/download/
- Cài bản Community (miễn phí)

## 3. Tạo connection

1. Mở DBeaver → **Database** → **New Database Connection**
2. Chọn **PostgreSQL** → Next
3. Điền thông tin (khớp `.env.example`):

| Trường | Giá trị |
|--------|---------|
| Host | `localhost` |
| Port | `5432` |
| Database | `qos_anomaly` |
| Username | `postgres` |
| Password | `secret` |

4. **Test Connection** → Finish

## 4. Xem schema

Mở rộng: `qos_anomaly` → `Schemas` → `public` → `Tables`

| Bảng | Mô tả |
|------|--------|
| `dataset_logs` | Log đầu vào đã ingest |
| `detection_results` | Kết quả phát hiện (`log_id`, `anomaly_score`, `is_anomaly`, `predicted_at`) |

## 5. Query mẫu

```sql
-- Xem log đã lưu
SELECT * FROM dataset_logs ORDER BY id DESC LIMIT 20;

-- Kết quả detection gần nhất
SELECT dr.id, dl.client_ip, dl.endpoint_uri, dr.anomaly_score, dr.is_anomaly, dr.predicted_at
FROM detection_results dr
JOIN dataset_logs dl ON dl.id = dr.log_id
ORDER BY dr.predicted_at DESC
LIMIT 50;

-- Thống kê anomaly
SELECT is_anomaly, COUNT(*) FROM detection_results GROUP BY is_anomaly;
```

## 6. Ghi chú

- Nếu connection refused: kiểm tra `docker compose ps`
- Đổi password: sửa `docker-compose.yml` và `DATABASE_URL` trong `.env`
- Streamlit demo có checkbox **Lưu kết quả vào PostgreSQL** sau mỗi lần predict
