# Hướng dẫn dataset train (domain ngân hàng)

## File chính

- `data/raw/train_logs_1000.csv` — 1000 bản ghi mô phỏng log API banking (đã gắn nhãn)
- `data/raw/train_real_template.csv` — mẫu nếu thay bằng log thật

## Schema

`timestamp,client_ip,endpoint_uri,http_method,response_time_ms,status_code,bytes_sent,is_anomaly,anomaly_type`

## Endpoint banking trong bộ mô phỏng

- `/api/v1/auth/login`, `/api/v1/auth/otp/verify`
- `/api/v1/accounts/balance`, `/api/v1/transfers/napas`
- `/api/v1/payments/bill`, `/api/v1/qr/pay`, …

## Anomaly

| Loại | Ý nghĩa banking |
|------|-----------------|
| spam | Brute-force login/OTP |
| high_latency | NAPAS / thanh toán timeout |
| system_error | Lỗi core 5xx |

## Train

```bash
python3 scripts/train_model.py --data data/raw/train_logs_1000.csv
```

Nếu có file thật (~1000 dòng đúng schema): lưu `data/raw/train_real_1000.csv` rồi train với path đó.
