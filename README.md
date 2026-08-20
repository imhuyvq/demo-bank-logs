# Phát hiện bất thường QoS

Đồ án phát hiện log HTTP bất thường bằng **Isolation Forest**. Phạm vi cố ý nhỏ: dataset mô phỏng, một model, một giao diện Streamlit và PostgreSQL Docker chỉ để lưu kết quả. Không API, biểu đồ hay báo cáo sinh tự động.

## Chức năng

1. Sinh 1.000 log API ngân hàng mô phỏng.
2. Làm sạch CSV theo 7 cột log bắt buộc.
3. Biến đổi thành 14 feature QoS.
4. Huấn luyện một Isolation Forest.
5. Chọn ngưỡng trên validation có nhãn mô phỏng.
6. Dự đoán bình thường/bất thường, tùy chọn lưu vào PostgreSQL Docker.

## Chạy

```bash
python3 -m pip install -e ".[dev]"
make pipeline
make test
make db-up
make app
```

Mở app tại URL Streamlit in ra terminal.

## Cấu trúc

```text
app/streamlit_app.py            giao diện một trang
data/raw/train_logs_1000.csv    dataset mẫu mô phỏng
scripts/generate_dataset.py     sinh dữ liệu
scripts/train_model.py          train và lưu model
scripts/evaluate_model.py       in metric test
src/qos_anomaly/data/           generator, loader, feature
src/qos_anomaly/model/          train, predict, evaluate
src/qos_anomaly/db/             lưu PostgreSQL tối giản
sql/schema.sql                   schema PostgreSQL
docker-compose.yml               PostgreSQL Docker
tests/                          kiểm thử lõi
docs/GIAI_THICH_HE_THONG.md     tài liệu bảo vệ đầy đủ
```

## PostgreSQL Docker

DB là tùy chọn, chỉ lưu kết quả khi tick checkbox trong app:

```bash
make db-up
make db-down
```

Lần đầu tạo DB tự động từ `sql/schema.sql`. Nếu Docker báo volume cũ dùng cấu hình user/password khác, không xóa ngay. Backup dữ liệu trước. Reset sạch chỉ khi không cần lịch sử:

```bash
docker compose down -v
make db-up
```

## Dữ liệu và giới hạn

`train_logs_1000.csv` do `src/qos_anomaly/data/generator.py` tạo, không phải log ngân hàng thật. Model chỉ dự đoán nhị phân; `spam`, `high_latency`, `system_error` là nhãn kịch bản để sinh và đánh giá dữ liệu.

Chi tiết nghiệp vụ, thuật toán, feature, metric, giới hạn và tài liệu tham khảo: [`docs/GIAI_THICH_HE_THONG.md`](docs/GIAI_THICH_HE_THONG.md).
