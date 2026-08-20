# Giải thích toàn diện hệ thống phát hiện bất thường QoS

## 1. Mục tiêu nghiệp vụ

Hệ thống hỗ trợ người vận hành API phát hiện log HTTP có dấu hiệu bất thường để kiểm tra sớm sự cố chất lượng dịch vụ (QoS) hoặc hành vi truy cập đáng ngờ.

Đầu vào là file CSV log HTTP. Đầu ra là mỗi log được gắn:

- `anomaly_score`: điểm bất thường;
- `is_anomaly_pred = 1`: bất thường;
- `is_anomaly_pred = 0`: bình thường.

Người vận hành có thể lưu lần dự đoán vào PostgreSQL chạy bằng Docker để đối chiếu sau này. Database chỉ lưu kết quả, **không tham gia train hoặc dự đoán**.

## 2. Phạm vi cố ý giữ nhỏ

Hệ thống giữ đúng một luồng:

```mermaid
flowchart TD
    A[CSV log] --> B[Kiểm tra schema và làm sạch]
    B --> C[Tạo 14 feature]
    C --> D[Isolation Forest]
    D --> E[anomaly score]
    E --> F{score >= threshold}
    F -->|Có| G[Bất thường]
    F -->|Không| H[Bình thường]
    G --> I[Streamlit]
    H --> I
    I --> J[(PostgreSQL Docker tùy chọn)]
```

Không có API, model registry, nhiều model, biểu đồ phức tạp, EDA hay báo cáo sinh tự động. Các phần này không cần cho mục tiêu demo và dễ làm đồ án khó giải thích.

## 3. Cấu trúc file còn lại

| Vai trò | File |
|---|---|
| Giao diện một trang | `app/streamlit_app.py` |
| Cấu hình/path | `src/qos_anomaly/config.py` |
| Sinh data mô phỏng | `src/qos_anomaly/data/generator.py` |
| Đọc/làm sạch CSV | `src/qos_anomaly/data/loader.py` |
| Tạo feature | `src/qos_anomaly/data/features.py` |
| Train model | `src/qos_anomaly/model/train.py` |
| Predict | `src/qos_anomaly/model/predict.py` |
| Evaluate test | `src/qos_anomaly/model/evaluate.py` |
| Lưu PostgreSQL | `src/qos_anomaly/db/repository.py` |
| Khởi tạo DB | `sql/schema.sql` |
| Docker PostgreSQL | `docker-compose.yml` |
| Dataset mẫu | `data/raw/train_logs_1000.csv` |
| Model đã train | `models/isolation_forest_bundle.joblib` |
| Kiểm thử lõi | `tests/` |

## 4. Dữ liệu lấy từ đâu?

### 4.1 Nguồn dữ liệu

`data/raw/train_logs_1000.csv` do code `src/qos_anomaly/data/generator.py` sinh. Đây là dữ liệu **mô phỏng**, không phải log ngân hàng thật, không phải KDD và không lấy từ production.

Lý do: log ngân hàng thật có thể chứa IP, endpoint nội bộ, mã giao dịch hoặc dữ liệu khách hàng; project không có quyền dùng dữ liệu đó.

### 4.2 Dataset hiện tại

- 1.000 log;
- seed cố định `42`, giúp tái lập;
- khoảng 8% bất thường;
- 14 endpoint API ngân hàng giả lập;
- IP private dạng `10.x.x.x`.

### 4.3 Ba kịch bản mô phỏng

| Kịch bản | Cách sinh | Ý nghĩa nghiệp vụ |
|---|---|---|
| `spam` | một IP gửi burst login/OTP sát nhau; status thiên về 401/403/429 | brute-force hoặc thử OTP quá nhiều |
| `high_latency` | latency 3500–18000 ms | cổng thanh toán/core service phản hồi chậm |
| `system_error` | status 500/502/503 | lỗi server, middleware hoặc downstream service |

`anomaly_type` là nhãn do generator tạo để kiểm tra mô hình. Model không dự đoán loại này; model chỉ dự đoán bất thường hay không.

### 4.4 Giới hạn dữ liệu

Normal và anomaly được sinh theo luật khá khác nhau. F1 trên dataset này chỉ chứng minh pipeline hoạt động trên dữ liệu mô phỏng. Không được kết luận model chính xác tương đương trên log production.

## 5. Schema CSV

Bảy cột bắt buộc:

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `timestamp` | ISO 8601 | thời điểm request |
| `client_ip` | chuỗi | IP gửi request |
| `endpoint_uri` | chuỗi | API được gọi |
| `http_method` | chuỗi | GET, POST, PUT, DELETE... |
| `response_time_ms` | số | latency, đơn vị ms |
| `status_code` | số nguyên | HTTP status |
| `bytes_sent` | số nguyên | kích thước response |

Hai cột chỉ cần trong CSV train/evaluate:

| Cột | Ý nghĩa |
|---|---|
| `is_anomaly` | nhãn tham chiếu 0/1 |
| `anomaly_type` | kịch bản generator |

CSV upload để predict không cần hai cột nhãn.

## 6. Làm sạch dữ liệu

`clean_logs()` làm các việc sau theo thứ tự:

1. chấp nhận alias `response_time` rồi đổi thành `response_time_ms`;
2. kiểm tra bảy cột bắt buộc;
3. parse `timestamp`;
4. ép latency, status, bytes thành số;
5. bỏ dòng không parse được trường bắt buộc;
6. clip latency âm về `0`;
7. bỏ status ngoài khoảng HTTP hợp lệ `100–599`;
8. chuẩn hóa method thành chữ hoa;
9. sắp dữ liệu theo thời gian.

Sắp thời gian là bắt buộc vì request rate và train/test split đều phụ thuộc thời điểm log.

## 7. Feature engineering

`FeatureBuilder` biến mỗi log thành 14 số:

| Feature | Công thức/nguồn | Lý do |
|---|---|---|
| `response_time_log1p` | `log(1 + latency)` | giảm lệch latency rất lớn |
| `status_class` | `status_code // 100` | nhóm 2xx/4xx/5xx |
| `is_5xx` | status >= 500 | đánh dấu lỗi server |
| `is_4xx` | 400 <= status < 500 | đánh dấu lỗi client/auth |
| `request_rate` | số log cùng IP trong 60 giây | nhận burst request |
| `hour_sin`, `hour_cos` | sin/cos theo giờ | giờ có tính chu kỳ; 23h gần 0h |
| `dow_sin`, `dow_cos` | sin/cos theo ngày tuần | biểu diễn chu kỳ tuần |
| `endpoint_freq` | tần suất endpoint trong train | endpoint hiếm có thể đáng chú ý |
| `method_code` | GET=0, POST=1... | đưa method vào model số |
| `bytes_sent_log1p` | `log(1 + bytes)` | giảm lệch response size |
| `ip_error_rate` | tỷ lệ status >=400 theo IP ở train | lịch sử lỗi IP |
| `ip_avg_latency` | latency trung bình IP ở train | hành vi latency IP |

Các thống kê endpoint/IP chỉ fit trên train. Test không được dùng để học statistics; đây là cách tránh **data leakage**.

### Giới hạn request rate

`request_rate` được tính trong batch CSV hiện có. Upload một record đơn lẻ luôn gần rate `1`; hệ thống chưa có state lưu lịch sử request giữa nhiều lần upload. Vì vậy demo này phù hợp batch/offline, không phải real-time streaming.

## 8. Thuật toán: Isolation Forest

### 8.1 Vì sao chọn?

Isolation Forest phù hợp khi anomaly hiếm và không có nhãn production đáng tin cậy. Thuật toán xử lý feature số, train nhanh cho dataset nhỏ và dễ giải thích.

### 8.2 Nguyên lý

Mỗi cây thực hiện nhiều lần:

1. chọn ngẫu nhiên một feature;
2. chọn ngẫu nhiên điểm cắt trong khoảng min–max feature;
3. chia log thành hai nhánh;
4. lặp đến khi log bị cô lập.

Log khác biệt với phần lớn dữ liệu thường bị cô lập trong ít bước hơn. Đường đi trong cây ngắn hơn nghĩa là có xu hướng bất thường hơn.

Công thức score trong bài báo gốc:

```text
s(x, n) = 2 ^ (-E[h(x)] / c(n))
```

`h(x)` là độ dài đường đi cô lập log `x`; `E` là trung bình qua nhiều cây; `c(n)` là hệ số chuẩn hóa theo số mẫu.

Project dùng `sklearn` rồi quy ước:

```python
anomaly_score = -model.decision_function(X)
```

Do đó score càng cao càng bất thường. Quy tắc cuối:

```text
is_anomaly_pred = 1 khi anomaly_score >= threshold
```

### 8.3 Tham số cố định

| Tham số | Giá trị | Ý nghĩa |
|---|---:|---|
| `n_estimators` | 300 | số cây |
| `contamination` | 0.08 | tỷ lệ anomaly dự kiến |
| `max_features` | 1.0 | dùng toàn bộ feature cho mỗi cây |
| `max_samples` | `auto` | sklearn tự chọn số sample/cây |
| `random_state` | 42 | tái lập kết quả |

Không grid search. Dataset nhỏ; một cấu hình cố định ít code, train nhanh và dễ bảo vệ hơn.

### 8.4 Vì sao không StandardScaler?

Isolation Forest là cây chia theo feature, không phải thuật toán khoảng cách như KNN/SVM. Scale tuyến tính không cần cho các phép split này, nên project bỏ StandardScaler.

## 9. Train, validation, test

Dữ liệu chia theo thời gian:

- 70% train: học cấu trúc bình thường;
- 15% validation: chọn threshold;
- 15% test: metric cuối.

Luồng train:

1. load CSV có nhãn;
2. sort và chia 70/15/15;
3. fit feature statistics trên train;
4. fit Isolation Forest trên `X_train`, không dùng `y_train`;
5. thử 200 threshold từ percentile score 1 đến 99 trên validation;
6. chọn threshold có F1 validation cao nhất;
7. đo F1 test;
8. lưu model, feature maps, threshold vào `models/isolation_forest_bundle.joblib`.

Cách gọi chính xác:

> Isolation Forest fit không giám sát. Nhãn mô phỏng chỉ dùng hiệu chỉnh threshold ở validation và đánh giá ở test.

## 10. Kết quả và cách đọc

Chạy:

```bash
make eval
```

Script in `precision`, `recall`, `f1`, `accuracy`, `false_positive_rate` và confusion matrix.

| Metric | Công thức | Ý nghĩa |
|---|---|---|
| Precision | TP / (TP + FP) | bao nhiêu cảnh báo là đúng |
| Recall | TP / (TP + FN) | bắt được bao nhiêu anomaly thật |
| F1 | trung bình điều hòa precision/recall | metric chính cho lớp anomaly hiếm |
| FPR | FP / (FP + TN) | tỷ lệ báo nhầm normal |
| Accuracy | (TP + TN) / tổng | chỉ dùng tham khảo vì normal nhiều |

Không gọi kết quả này là production-ready/pilot-ready. Test nhỏ và cùng generator với train.

## 11. Streamlit

Chạy:

```bash
make app
```

Một trang có:

1. chọn CSV mẫu hoặc upload CSV;
2. xem số dòng gốc/hợp lệ/bị loại;
3. chỉnh threshold;
4. chạy Detection;
5. xem tổng số, số anomaly, bảng kết quả;
6. tải CSV kết quả;
7. tùy chọn lưu kết quả vào PostgreSQL.

Không cần bấm lưu DB để model chạy.

## 12. PostgreSQL bằng Docker

### 12.1 Vai trò DB

Bảng duy nhất là `detection_results`. Mỗi dòng lưu:

- timestamp, IP, endpoint, latency, status từ log;
- anomaly score;
- cờ anomaly;
- thời điểm ghi DB.

Schema: `sql/schema.sql`.

### 12.2 Chạy DB

```bash
docker compose up -d
```

Kiểm tra:

```bash
docker compose ps
```

Dừng:

```bash
docker compose down
```

Xóa cả dữ liệu Docker volume, chỉ khi chắc chắn không cần lịch sử:

```bash
docker compose down -v
```

PostgreSQL mặc định:

```text
host: localhost
port: 5432
database: qos_anomaly
user: postgres
password: secret
```

Connection URL:

```text
postgresql+psycopg2://postgres:secret@localhost:5432/qos_anomaly
```

Trong app, tick **Lưu kết quả vào PostgreSQL**, sau đó bấm chạy model. Nếu Docker DB tắt, app báo lỗi lưu nhưng không làm mất kết quả dự đoán trên giao diện.

## 13. Thư viện

| Thư viện | Lý do |
|---|---|
| NumPy | toán số, sin/cos, random |
| pandas | CSV, cleaning, group data |
| scikit-learn | Isolation Forest và metrics |
| joblib | lưu/load model bundle |
| Streamlit | UI demo |
| SQLAlchemy + psycopg2 | ghi PostgreSQL |
| pytest | test lõi |

Không dùng FastAPI, Plotly, Matplotlib, Seaborn, Jupyter, Docker client Python hay deep learning.

## 14. Câu hỏi bảo vệ

### Dữ liệu thật hay giả?

Giả lập bằng `generator.py`. Không nói là dữ liệu ngân hàng thật.

### Model có phân loại spam/high latency/system error không?

Không. Output chỉ 0/1. Ba loại là nhãn generator để đánh giá.

### Vì sao dùng nhãn nếu gọi unsupervised?

Model fit không truyền nhãn. Nhãn validation chỉ chọn threshold, nhãn test tính metrics.

### Vì sao F1 có thể cao?

Luật generator tạo anomaly khá tách biệt normal. Kết quả không bảo đảm cho production.

### Một record có phát hiện spam được không?

Không tốt. Feature request rate cần batch cùng IP trong 60 giây. Muốn real-time cần lưu state/streaming, nằm ngoài phạm vi.

### DB dùng làm gì?

Chỉ lưu kết quả prediction để truy vết. DB không làm model thông minh hơn và không chứa model.

### Vì sao không dùng nhiều thuật toán?

Mục tiêu đồ án là giải thích một pipeline đúng và tái lập được. Thêm nhiều model không có baseline/data thật sẽ tăng phức tạp, không tăng giá trị.

## 15. Cách tái lập

```bash
python3 -m pip install -e ".[dev]"
make data
make train
make eval
make test
docker compose up -d
make app
```

## 16. Tài liệu tham khảo

1. Liu, Ting, Zhou. *Isolation Forest*. IEEE ICDM 2008. DOI: https://doi.org/10.1109/ICDM.2008.17
2. Liu, Ting, Zhou. *Isolation-based Anomaly Detection*. ACM TKDD 2012. DOI: https://doi.org/10.1145/2133360.2133363
3. scikit-learn IsolationForest: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
4. scikit-learn Outlier Detection: https://scikit-learn.org/stable/modules/outlier_detection.html
5. scikit-learn metric evaluation: https://scikit-learn.org/stable/modules/model_evaluation.html
6. RFC 9110 HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110
7. PostgreSQL documentation: https://www.postgresql.org/docs/
8. Streamlit documentation: https://docs.streamlit.io/
