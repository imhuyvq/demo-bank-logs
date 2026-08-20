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

Không có API, model registry, nhiều model, EDA hay báo cáo sinh tự động. Dashboard giữ bốn tab cần demo: phát hiện, trực quan kết quả, lịch sử PostgreSQL và thông tin model.

## 3. Cấu trúc file còn lại

| Vai trò | File |
|---|---|
| Dashboard 4 tab | `app/streamlit_app.py` |
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

Dashboard có bốn tab:

1. **Phát hiện:** chọn CSV mẫu, upload CSV hoặc nhập tay; kiểm tra số dòng; chỉnh threshold; chạy model; lọc/tải CSV kết quả; tùy chọn lưu PostgreSQL.
2. **Trực quan:** anomaly score theo thời gian, HTTP status, latency theo log, tỷ lệ nhãn dự đoán của batch gần nhất.
3. **Lịch sử SQL:** tải batch kết quả đã lưu từ PostgreSQL; chọn số dòng muốn xem.
4. **Thông tin model:** thuật toán, threshold, tham số, F1 mô phỏng và danh sách feature.

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

## 16. Đọc code theo từng luồng chạy

### 16.1 Luồng sinh dataset: `make data`

Lệnh thực tế:

```bash
python3 scripts/generate_dataset.py --n-rows 1000
```

Trình tự hàm:

```text
scripts/generate_dataset.py
  → generate_logs(n_rows=1000, anomaly_ratio=0.08, seed=42)
  → save_dataset(...)
  → data/raw/train_logs_1000.csv
```

`generate_logs()` tạo `numpy.random.Generator` bằng `np.random.default_rng(seed)`. Pseudo-random generator cùng seed tạo lại cùng chuỗi số ngẫu nhiên. Vì vậy cùng Python/library version và seed `42` sẽ sinh dataset giống nhau.

Hàm sinh normal trước, sau đó chia số anomaly theo tỷ lệ:

```text
n_anomaly = int(n_rows × anomaly_ratio)
n_normal  = n_rows - n_anomaly
n_spam    = int(n_anomaly × 0.35)
n_latency = int(n_anomaly × 0.35)
n_error   = n_anomaly - n_spam - n_latency
```

Sau khi ghép các record, DataFrame được sort theo `timestamp`. Generator kiểm tra đủ `LOG_COLUMNS + LABEL_COLUMNS` trước khi trả về. Đây là kiểm tra lập trình, không phải kiểm định tính thực tế nghiệp vụ.

### 16.2 Luồng train: `make train`

Lệnh thực tế:

```bash
python3 scripts/train_model.py --data data/raw/train_logs_1000.csv
```

Trình tự hàm chi tiết:

```text
train_pipeline(data_path)
  1. load_logs(data_path, require_labels=True)
  2. chronological_split(df)
  3. FeatureBuilder.fit(train_df)
  4. FeatureBuilder.transform(train_df/val_df/test_df)
  5. train_isolation_forest(X_train, X_val, y_val)
  6. anomaly_scores(model, X_val)
  7. find_best_threshold(scores, y_val)
  8. anomaly_scores(model, X_test)
  9. joblib.dump(bundle, models/isolation_forest_bundle.joblib)
```

`chronological_split()` không shuffle. Nếu có `n` dòng:

```text
train     = df[0 : int(0.70 × n)]
validation = df[int(0.70 × n) : int(0.85 × n)]
test      = df[int(0.85 × n) : n]
```

Với 1.000 dòng: 700 train, 150 validation, 150 test.

**Lý do không shuffle:** mô phỏng việc train từ log quá khứ và đo trên log đến sau. Tuy nhiên dataset mô phỏng không có drift thực tế, nên đây chỉ là cấu trúc split hợp lý chứ chưa chứng minh độ bền theo thời gian.

### 16.3 Object bundle được lưu

`joblib.dump()` ghi một Python dictionary xuống file nhị phân `.joblib`. Bundle hiện chứa:

| Key | Kiểu/nguồn | Dùng khi predict |
|---|---|---|
| `model` | `sklearn.ensemble.IsolationForest` đã fit | tính `decision_function` |
| `feature_builder` | dictionary từ `FeatureBuilder.to_dict()` | tái tạo feature maps train |
| `feature_columns` | list 14 tên feature | giữ thứ tự input model |
| `threshold` | float | quyết định nhãn 0/1 |
| `best_params` | dictionary cấu hình cố định | hiển thị/tái lập train |
| `metrics_val` | F1 validation | metadata |
| `metrics_test_preview` | F1 test lúc train | metadata |
| `trained_at` | ISO datetime UTC | metadata |
| `sklearn_version` | version sklearn lúc train | kiểm tra tương thích môi trường |

`FeatureBuilder.to_dict()` lưu các map học từ train:

```text
endpoint_freq_map
ip_error_rate_map
ip_avg_latency_map
global_median_latency
rate_window_seconds
```

Không lưu raw train dataset trong bundle. Không lưu nhãn test. Khi predict log mới, code dùng map đã học; endpoint/IP chưa thấy ở train nhận giá trị fallback.

**Lưu ý an toàn:** `joblib.load()` có thể thực thi pickle object. Chỉ load file model do project train hoặc nguồn tin cậy tạo. Không nhận file `.joblib` do người dùng upload.

### 16.4 Luồng predict trong app

Khi mở `app/streamlit_app.py`:

1. thêm `src/` vào `sys.path`, để Python import package `qos_anomaly`;
2. `st.set_page_config()` cấu hình title/layout trước UI;
3. `get_bundle()` chạy `load_bundle()` lần đầu;
4. `@st.cache_resource` giữ model trong process Streamlit, tránh đọc disk mỗi rerun;
5. người dùng chọn CSV mẫu hoặc upload CSV;
6. `clean_logs(raw_df)` kiểm tra và chuẩn hóa input;
7. khi bấm nút, `predict_dataframe(input_df, bundle, threshold)` chạy;
8. kết quả lưu ở `st.session_state["result"]` để vẫn còn sau rerun do widget;
9. DataFrame hiển thị hoặc tải lại thành CSV;
10. nếu tick DB, `save_results(result)` insert từng kết quả vào PostgreSQL.

`predict_dataframe()` không fit lại feature map và không train lại model. Nó chỉ:

```python
work = clean_logs(df)
fb = FeatureBuilder.from_dict(bundle["feature_builder"])
X = fb.transform(work).values
scores = -bundle["model"].decision_function(X)
is_anomaly = (scores >= threshold).astype(int)
```

Đây là điểm phải nhớ khi bảo vệ: **fit chỉ xuất hiện lúc train; transform xuất hiện ở cả train và predict.**

## 17. Chi tiết `FeatureBuilder`

### 17.1 `fit()` học gì?

`FeatureBuilder.fit(train_df)` không học model ML. Nó chỉ học các thống kê cần đổi chuỗi/log thành số:

```python
endpoint_freq_map_ = train_df["endpoint_uri"].value_counts(normalize=True)
ip_error_rate_map_ = mean(status_code >= 400) group by client_ip
ip_avg_latency_map_ = mean(response_time_ms) group by client_ip
global_median_latency_ = median(response_time_ms)
```

Ví dụ train có 700 log, endpoint `/login` xuất hiện 70 lần:

```text
endpoint_freq[/login] = 70 / 700 = 0.10
```

Nếu IP `10.0.0.8` có 10 request, trong đó 3 request status >= 400:

```text
ip_error_rate[10.0.0.8] = 3 / 10 = 0.30
```

### 17.2 `transform()` tạo feature thế nào?

`transform()` copy DataFrame đầu vào, tạo DataFrame mới tên `features`, rồi thêm từng cột theo thứ tự `FEATURE_COLUMNS`. Cuối hàm:

```python
features = features[FEATURE_COLUMNS]
features = features.replace([np.inf, -np.inf], np.nan)
features = features.fillna(features.median(numeric_only=True))
return features.astype(float)
```

Kết quả luôn là ma trận số thực có kích thước:

```text
số dòng input × 14
```

Ví dụ 20 log upload tạo matrix `20 × 14`.

### 17.3 Log transform

Latency và bytes thường lệch phải: đa số nhỏ, vài giá trị rất lớn. Dùng:

```text
log1p(v) = ln(1 + v)
```

Ví dụ gần đúng:

| Giá trị gốc | `log1p` |
|---:|---:|
| 0 | 0 |
| 100 ms | 4.615 |
| 1.000 ms | 6.909 |
| 10.000 ms | 9.210 |

Transform vẫn giữ thứ tự lớn/nhỏ nhưng giảm khoảng cách số học. Isolation Forest không bắt buộc scale, nhưng log transform vẫn hợp lý để giảm ảnh hưởng giá trị cực lớn khi chọn split ngẫu nhiên.

### 17.4 Time cyclic encoding

Với giờ `h` từ 0 đến 23:

```text
hour_sin = sin(2πh / 24)
hour_cos = cos(2πh / 24)
```

Hai cột cùng mô tả một vị trí trên vòng tròn 24 giờ. Nếu chỉ dùng `hour=23` và `hour=0`, số học coi chênh 23; sin/cos coi hai thời điểm gần nhau.

Tương tự, `dow_sin`, `dow_cos` dùng ngày thứ hai=0 đến chủ nhật=6 trên vòng tròn 7 ngày.

### 17.5 Request rate: logic và độ phức tạp

Với mỗi `client_ip`, `_compute_request_rate()`:

1. lấy timestamp của IP đó và sort;
2. với từng timestamp `t`, đếm timestamp cùng IP trong `[t - 60 giây, t]`;
3. gán số đếm về index log tương ứng.

Ví dụ IP A có request tại 10:00:00, 10:00:10, 10:00:50, 10:01:20:

| Timestamp | Cửa sổ nhìn lại | `request_rate` |
|---|---|---:|
| 10:00:00 | 09:59:00–10:00:00 | 1 |
| 10:00:10 | 09:59:10–10:00:10 | 2 |
| 10:00:50 | 09:59:50–10:00:50 | 3 |
| 10:01:20 | 10:00:20–10:01:20 | 2 |

Code hiện tạo mask cho từng timestamp. Nếu một IP có `k` request, chi phí gần `O(k²)`. Với 1.000 log demo chấp nhận được. Với log production lớn, phải thay bằng rolling window vectorized hoặc stream aggregation; không nói code hiện tại phù hợp hàng triệu log.

### 17.6 Fallback cho giá trị mới

| Giá trị mới khi predict | Fallback |
|---|---|
| endpoint chưa thấy ở train | `endpoint_freq = 0.0` |
| IP chưa thấy ở train | `ip_error_rate = 0.0` |
| IP chưa thấy ở train | `ip_avg_latency = global_median_latency` |
| HTTP method không có trong map | `method_code = -1` |

Fallback ngăn NaN và giữ đúng 14 feature. Nó không có nghĩa model hiểu chính xác hành vi endpoint/IP mới.

## 18. Nguyên lý Isolation Forest chi tiết hơn

### 18.1 Một Isolation Tree không phải decision tree phân loại

Decision Tree phân loại thông thường chọn feature/threshold để giảm entropy hoặc Gini và cần nhãn. Isolation Tree:

- không dùng `y_train`;
- chọn feature ngẫu nhiên;
- chọn điểm cắt ngẫu nhiên giữa min/max feature tại node;
- mục tiêu là tách điểm, không tối ưu lớp.

Vì vậy Isolation Forest phù hợp với anomaly detection không nhãn.

### 18.2 Ví dụ cô lập trực quan

Giả sử feature `response_time_log1p` của normal thường quanh `4–7`, còn một log latency cao có value `9.5`.

Một split ngẫu nhiên, ví dụ `x < 8.2`, sẽ tách ngay log `9.5` ra nhánh nhỏ. Trong khi nhiều normal vẫn nằm chung nhánh và cần thêm split để tách từng điểm. Qua nhiều cây, log `9.5` có path length trung bình ngắn hơn, nên score bất thường cao hơn.

Không phải mọi anomaly đều chỉ khác một feature. Một log có latency vừa phải nhưng endpoint hiếm, 4xx cao, request rate lớn vẫn có thể bị cô lập sớm do tổ hợp split qua nhiều cây.

### 18.3 Path length và chuẩn hóa

Với mỗi tree `T`, gọi `h_T(x)` là số edge/node đi qua để cô lập x. Forest lấy trung bình:

```text
E[h(x)] = (h_T1(x) + h_T2(x) + ... + h_Tm(x)) / m
```

`m` là `n_estimators = 300`.

Hệ số chuẩn hóa lý thuyết:

```text
c(n) = 2H(n - 1) - 2(n - 1)/n
```

Trong đó `H(i)` là harmonic number, xấp xỉ `ln(i) + γ`, `γ` là hằng số Euler-Mascheroni. `c(n)` làm path length giữa cây có sample size khác nhau có thể so sánh.

Score bài báo:

```text
s(x, n) = 2 ^ (-E[h(x)] / c(n))
```

- `s` gần 1: dễ bị cô lập, nghi là anomaly;
- `s` quanh 0.5: giống dữ liệu bình thường;
- `s` nhỏ hơn 0.5: rất khó cô lập.

Project không tính công thức này trực tiếp. `scikit-learn` xử lý bên trong `score_samples()`/`decision_function()`.

### 18.4 `score_samples`, `offset_`, `decision_function`

Trong scikit-learn:

```text
decision_function(X) = score_samples(X) - offset_
```

Quy ước sklearn: `decision_function < 0` thường là outlier, `>= 0` là inlier theo threshold mặc định.

Project đảo dấu:

```text
anomaly_score = -decision_function(X)
```

Vì vậy UI dễ hiểu hơn: số lớn hơn nghĩa là đáng ngờ hơn.

`contamination=0.08` giúp sklearn đặt `offset_` theo tỷ lệ outlier kỳ vọng. Nhưng project lại chọn `threshold` riêng bằng F1 validation. Vì vậy contamination và threshold có phần vai trò chồng nhau. Cách trình bày chính xác:

> Contamination là prior tỷ lệ anomaly cho Isolation Forest. Quyết định cuối của project do threshold validation quyết định. Với production không có nhãn validation, có thể dùng threshold mặc định từ contamination hoặc threshold do vận hành đặt.

### 18.5 `max_samples='auto'`

Trong scikit-learn, `max_samples='auto'` dùng:

```text
min(256, số_dòng_train)
```

Với 700 train row, mỗi tree fit trên 256 sample được lấy ngẫu nhiên. Không phải mọi tree thấy cùng 256 dòng. Subsampling tăng đa dạng tree và giảm chi phí.

### 18.6 `max_features=1.0`

14 feature × `1.0` nghĩa mỗi tree được cấp toàn bộ 14 feature. Split tại từng node vẫn chọn ngẫu nhiên từ feature được cấp. Project không giảm feature subset vì 14 feature đã ít; dùng 1.0 làm pipeline dễ giải thích.

### 18.7 Vì sao không dùng nhãn lúc `fit`?

Dòng cốt lõi:

```python
model.fit(X_train)
```

Không có `y_train`. Model chỉ biết phân bố feature. `y_val` chỉ xuất hiện sau fit trong:

```python
f1_score(y_val, (scores >= threshold).astype(int))
```

Do đó đây là **unsupervised model + supervised threshold calibration trên dữ liệu mô phỏng**. Không gọi toàn bộ pipeline là unsupervised hoàn toàn.

## 19. Cơ chế chọn threshold và metric

### 19.1 `find_best_threshold()`

Hàm nhận vector score validation và nhãn validation.

1. lấy percentile 1 và 99 score, bỏ ảnh hưởng outlier cực đoan;
2. tạo 200 giá trị đều nhau trong khoảng đó bằng `np.linspace`;
3. tại mỗi ngưỡng `t`, dự đoán `score >= t`;
4. tính F1;
5. giữ `t` có F1 lớn nhất.

Pseudocode:

```text
best_f1 = 0
for t in 200 threshold:
    prediction = score >= t
    f1 = F1(y_validation, prediction)
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = t
```

Dùng percentile 1–99 thay vì min–max để một score bất thường cực lớn không kéo giãn toàn dải threshold.

### 19.2 Confusion matrix

| | Thực tế normal | Thực tế anomaly |
|---|---:|---:|
| Predict normal | TN | FN |
| Predict anomaly | FP | TP |

- TP: cảnh báo đúng;
- FP: báo động giả; người vận hành phải kiểm tra nhưng log thực bình thường;
- FN: bỏ sót anomaly; rủi ro QoS/security;
- TN: xác nhận normal đúng.

Threshold thấp hơn làm nhiều score vượt ngưỡng hơn: recall thường tăng, FP cũng có thể tăng. Threshold cao hơn làm cảnh báo ít hơn: precision có thể tăng, FN có thể tăng. F1 cân bằng hai phía nhưng không thay thế quyết định nghiệp vụ. Nếu bỏ sót lỗi thanh toán rất nguy hiểm, có thể chọn threshold ưu tiên recall thay vì F1.

## 20. Thư viện hoạt động cụ thể

### 20.1 `pandas`

Pandas cung cấp `DataFrame`, bảng dữ liệu có cột tên và index.

| Code | Tác dụng |
|---|---|
| `pd.read_csv(path)` | parse file CSV thành DataFrame |
| `pd.to_datetime(..., errors='coerce')` | parse thời gian; lỗi thành `NaT` để loại bỏ |
| `pd.to_numeric(..., errors='coerce')` | parse số; lỗi thành `NaN` |
| `dropna(subset=...)` | bỏ dòng thiếu trường bắt buộc |
| `groupby('client_ip')` | chia log theo IP để tính request rate/IP statistic |
| `value_counts(normalize=True)` | đếm tần suất endpoint thành tỷ lệ |
| `map(dictionary)` | đổi endpoint/IP/method thành giá trị đã học |
| `sort_values('timestamp')` | đảm bảo thứ tự thời gian |
| `to_csv(index=False)` | xuất kết quả từ app |

Pandas không phải thuật toán ML. Nó chuẩn bị bảng đúng kiểu trước khi đưa vào NumPy/scikit-learn.

### 20.2 `NumPy`

NumPy cung cấp `ndarray`, mảng số hiệu quả. Trong project nó dùng cho:

```python
np.log1p(...)      # log(1+x)
np.sin(...), np.cos(...)  # cyclic time feature
np.percentile(...) # biên threshold 1%, 99%
np.linspace(...)   # 200 threshold đều nhau
np.random.default_rng(42) # generator dataset tái lập
```

Sau `.values`, DataFrame feature thành NumPy matrix. Đây là input trực tiếp của `IsolationForest.fit()` và `decision_function()`.

### 20.3 `scikit-learn`

`scikit-learn` cung cấp hai nhóm:

1. **model:** `IsolationForest`;
2. **metrics:** `precision_score`, `recall_score`, `f1_score`, `accuracy_score`, `confusion_matrix`.

Luồng API model:

```python
model = IsolationForest(...)
model.fit(X_train)
raw_score = model.decision_function(X_predict)
```

`fit()` tạo 300 cây và học range/split từ train. `decision_function()` đi từng row qua 300 cây, lấy trung bình path length nội bộ, trả vector score có một phần tử cho mỗi row.

### 20.4 `joblib`

`joblib` serialize Python object, tối ưu phù hợp object chứa NumPy array. Project dùng đúng hai chỗ:

```python
joblib.dump(bundle, path)  # train
joblib.load(path)          # app/predict/evaluate
```

Lợi ích: app không train lại khi mở. Giá phải trả: bundle phụ thuộc compatibility Python/scikit-learn. Khi đổi logic feature hoặc đổi major version sklearn, cần train lại model.

### 20.5 `Streamlit`

Streamlit chạy file Python từ đầu mỗi khi người dùng đổi widget. Đây gọi là **rerun model**.

| API | Cơ chế |
|---|---|
| `st.radio`, `st.number_input`, `st.checkbox` | widget trả giá trị hiện tại rồi gây rerun khi đổi |
| `st.button` | trả `True` đúng một rerun sau click |
| `st.session_state` | dictionary giữ `result` qua rerun trong session browser |
| `@st.cache_resource` | giữ model object cho process, phù hợp resource nặng/không serialize UI |
| `@st.cache_data` | cache DataFrame dataset mẫu; copy-safe cho data |
| `st.dataframe` | render DataFrame vào browser |
| `st.download_button` | gửi bytes CSV cho browser download |

Không dùng CSS custom hay component JavaScript. UI dùng native Streamlit để ít code và dễ chạy.

### 20.6 `SQLAlchemy` và `psycopg2`

`psycopg2` là DBAPI driver: gửi protocol PostgreSQL từ Python sang server PostgreSQL.

SQLAlchemy trong project không dùng ORM. Nó làm hai việc:

```python
engine = create_engine(url)
statement = text("INSERT INTO ... VALUES (:timestamp, ...)")
```

`save_results()` tạo list dictionary parameter cho từng row. `connection.execute(statement, rows)` dùng bind parameter `:timestamp`, `:client_ip`, ... thay vì nối chuỗi SQL. Điều này tránh SQL injection từ IP, endpoint hoặc dữ liệu user upload.

`with create_engine(url).begin()` tạo transaction:

- mọi row insert thành công: tự `COMMIT` khi ra block;
- có exception: tự `ROLLBACK`;
- tránh lưu nửa batch.

### 20.7 Docker Compose và PostgreSQL

`docker-compose.yml` mô tả một service `db` từ image `postgres:16-alpine`.

| Phần | Ý nghĩa |
|---|---|
| `image: postgres:16-alpine` | PostgreSQL 16, Linux Alpine nhỏ |
| `ports: 5432:5432` | mở DB container ra `localhost:5432` |
| `POSTGRES_*` | tạo database/user/password ở lần init volume đầu tiên |
| volume `qos_pg_data` | dữ liệu còn sau `docker compose down` |
| bind mount `sql/schema.sql` | chạy schema khi volume DB hoàn toàn mới |
| `healthcheck` | Docker gọi `pg_isready` kiểm tra DB sẵn sàng |

**Điểm quan trọng:** Docker init scripts chỉ chạy lúc volume rỗng lần đầu. Đổi `POSTGRES_USER` hoặc đổi `sql/schema.sql` sau khi volume đã có sẽ không tự áp dụng. Phải migration schema riêng hoặc, với demo không cần giữ data, `docker compose down -v` rồi `make db-up`.

## 21. Luồng PostgreSQL từng bước

Khi user tick checkbox và bấm chạy:

```text
predict_dataframe
  → result DataFrame
  → save_results(result)
  → list[dict] parameter rows
  → SQLAlchemy Engine
  → psycopg2
  → PostgreSQL container
  → INSERT detection_results
  → COMMIT
```

`sql/schema.sql` tạo bảng gồm:

| Cột DB | Nguồn |
|---|---|
| `id` | PostgreSQL `BIGSERIAL` tự tăng |
| `timestamp` | timestamp log gốc |
| `client_ip` | log gốc |
| `endpoint_uri` | log gốc |
| `response_time_ms` | log gốc |
| `status_code` | log gốc |
| `anomaly_score` | output Isolation Forest |
| `is_anomaly` | `is_anomaly_pred` chuyển bool |
| `predicted_at` | UTC lúc ghi DB |

Không lưu `http_method`, `bytes_sent`, `anomaly_type` để schema gọn. Nếu sau này cần audit toàn bộ raw log, thêm migration có chủ đích; không tự thêm tất cả cột chỉ vì dataset có chúng.

## 22. Quy trình demo trước GV

1. Mở terminal thứ nhất:

   ```bash
   make db-up
   ```

2. Kiểm tra container healthy:

   ```bash
   docker compose ps
   ```

3. Mở terminal thứ hai:

   ```bash
   make app
   ```

4. Trong Streamlit: chọn **Bộ mẫu**, tick **Lưu kết quả vào PostgreSQL**, bấm **Chạy Isolation Forest**.

5. Giải thích bảng kết quả: threshold, score, cờ 0/1.

6. Xác minh DB nếu cần:

   ```bash
   docker compose exec -T db psql -U postgres -d qos_anomaly \
     -c "SELECT id, endpoint_uri, anomaly_score, is_anomaly, predicted_at FROM detection_results ORDER BY id DESC LIMIT 10;"
   ```

7. Nói rõ: DB chứng minh lưu kết quả; không chứng minh model production-ready.

## 23. Rủi ro kỹ thuật và hướng nâng cấp đúng thứ tự

| Rủi ro hiện tại | Tác động | Bước nâng cấp đúng |
|---|---|---|
| data mô phỏng | F1 lạc quan | dùng log staging/production đã ẩn danh |
| test chỉ 150 dòng | metric dao động | tăng dữ liệu, nhiều time split/seed |
| request rate theo batch | không real-time spam | state store/stream window theo IP |
| `O(k²)` rate/IP | chậm batch IP lớn | rolling window vectorized |
| threshold chọn theo synthetic label | không chắc hợp production | vận hành calibrate threshold, feedback label |
| IP raw trong DB | rủi ro privacy | hash/anonymize IP, retention policy, access control |
| password Docker mặc định | chỉ hợp local demo | secrets manager/biến môi trường production |
| joblib object | rủi ro file không tin cậy | chỉ load model internal, model signing/version policy |

Không thêm deep learning, Kafka, Redis hoặc microservice trước khi có log thật và số liệu chứng minh cần thiết.

## 24. Bản đồ đường dẫn code theo nghiệp vụ

> Cách đọc bảng: mở đường dẫn, tìm tên hàm/symbol bằng `Ctrl+F`. Tên hàm ổn định hơn số dòng vì line number thay đổi khi format hoặc thêm comment.

| Câu hỏi nghiệp vụ/kỹ thuật | Đường dẫn code | Symbol cần xem |
|---|---|---|
| Dataset lấy từ đâu? | [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) | `generate_logs()` |
| Normal log sinh thế nào? | [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) | `_normal_row()` |
| Spam/OTP burst sinh thế nào? | [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) | `_spam_rows()` |
| High latency sinh thế nào? | [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) | `_high_latency_row()` |
| System error sinh thế nào? | [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) | `_system_error_row()` |
| Dataset CSV được lưu ở đâu? | [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) | `save_dataset()` |
| Cột bắt buộc định nghĩa ở đâu? | [`src/qos_anomaly/config.py`](../src/qos_anomaly/config.py) | `LOG_COLUMNS`, `LABEL_COLUMNS` |
| Feature list định nghĩa ở đâu? | [`src/qos_anomaly/config.py`](../src/qos_anomaly/config.py) | `FEATURE_COLUMNS` |
| Schema CSV được kiểm tra thế nào? | [`src/qos_anomaly/data/loader.py`](../src/qos_anomaly/data/loader.py) | `validate_log_schema()` |
| Dữ liệu lỗi được làm sạch thế nào? | [`src/qos_anomaly/data/loader.py`](../src/qos_anomaly/data/loader.py) | `clean_logs()` |
| CSV được nạp thế nào? | [`src/qos_anomaly/data/loader.py`](../src/qos_anomaly/data/loader.py) | `load_logs()` |
| Request rate 60 giây tính thế nào? | [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) | `FeatureBuilder._compute_request_rate()` |
| Sin/cos thời gian tính thế nào? | [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) | `FeatureBuilder._time_features()` |
| Statistics train học gì? | [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) | `FeatureBuilder.fit()` |
| 14 feature được tạo thế nào? | [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) | `FeatureBuilder.transform()` |
| Feature maps được lưu thế nào? | [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) | `to_dict()`, `from_dict()` |
| Train/validation/test chia thế nào? | [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) | `chronological_split()` |
| Score đảo dấu ở đâu? | [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) | `anomaly_scores()` |
| Threshold F1 chọn thế nào? | [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) | `find_best_threshold()` |
| Isolation Forest khởi tạo ở đâu? | [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) | `train_isolation_forest()` |
| Pipeline train đầy đủ ở đâu? | [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) | `train_pipeline()` |
| Model bundle load thế nào? | [`src/qos_anomaly/model/predict.py`](../src/qos_anomaly/model/predict.py) | `load_bundle()` |
| Một batch được predict thế nào? | [`src/qos_anomaly/model/predict.py`](../src/qos_anomaly/model/predict.py) | `predict_dataframe()` |
| Metric test tính ở đâu? | [`src/qos_anomaly/model/evaluate.py`](../src/qos_anomaly/model/evaluate.py) | `evaluate_model()` |
| App load/cache model ở đâu? | [`app/streamlit_app.py`](../app/streamlit_app.py) | `get_bundle()` |
| App nhận CSV ở đâu? | [`app/streamlit_app.py`](../app/streamlit_app.py) | khối `source == "Bộ mẫu"` |
| Nút chạy model ở đâu? | [`app/streamlit_app.py`](../app/streamlit_app.py) | khối `st.button("Chạy Isolation Forest")` |
| Checkbox lưu DB ở đâu? | [`app/streamlit_app.py`](../app/streamlit_app.py) | `save_to_db` |
| Insert PostgreSQL ở đâu? | [`src/qos_anomaly/db/repository.py`](../src/qos_anomaly/db/repository.py) | `save_results()` |
| Đọc lịch sử SQL ở đâu? | [`src/qos_anomaly/db/repository.py`](../src/qos_anomaly/db/repository.py) | `load_recent_results()` |
| Bảng PostgreSQL định nghĩa ở đâu? | [`sql/schema.sql`](../sql/schema.sql) | `CREATE TABLE detection_results` |
| Docker DB cấu hình ở đâu? | [`docker-compose.yml`](../docker-compose.yml) | service `db` |
| Lệnh chạy project ở đâu? | [`Makefile`](../Makefile) | `data`, `train`, `eval`, `db-up`, `app`, `test` |
| Dependency nằm ở đâu? | [`pyproject.toml`](../pyproject.toml) | `[project].dependencies` |
| Test feature ở đâu? | [`tests/test_features.py`](../tests/test_features.py) | các hàm `test_*` |
| Test loader ở đâu? | [`tests/test_loader.py`](../tests/test_loader.py) | các hàm `test_*` |
| Test train/predict ở đâu? | [`tests/test_predict.py`](../tests/test_predict.py) | `test_predict_dataframe()` |

## 25. Đoạn code cốt lõi kèm giải thích

### 25.1 Sinh tỷ lệ normal/anomaly

**Nguồn:** [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) — `generate_logs()`

```python
rng = np.random.default_rng(seed)
n_anomaly = int(n_rows * anomaly_ratio)
n_normal = n_rows - n_anomaly

n_spam = int(n_anomaly * 0.35)
n_latency = int(n_anomaly * 0.35)
n_error = n_anomaly - n_spam - n_latency
```

Với `n_rows=1000`, `anomaly_ratio=0.08`:

```text
n_anomaly = 80
n_normal = 920
n_spam = 28
n_latency = 28
n_error = 24
```

`rng` là NumPy random generator có seed. Mọi hàm sinh row dùng chung object này nên chuỗi random tái lập được.

### 25.2 Sinh spam theo burst

**Nguồn:** [`src/qos_anomaly/data/generator.py`](../src/qos_anomaly/data/generator.py) — `_spam_rows()`

```python
for i in range(n_burst):
    ts = base_ts + timedelta(milliseconds=int(200 + i * 150))
    rows.append(
        {
            "client_ip": client_ip,
            "endpoint_uri": endpoint,
            "http_method": "POST",
            "status_code": int(
                rng.choice([401, 403, 429, 200], p=[0.45, 0.2, 0.25, 0.1])
            ),
            "is_anomaly": 1,
            "anomaly_type": "spam",
        }
    )
```

Cùng `client_ip`, cùng login/OTP endpoint và timestamp cách nhau 150 ms tạo dấu hiệu burst. `request_rate` sau đó có thể nhận ra nhiều request cùng IP trong 60 giây.

### 25.3 Kiểm tra schema

**Nguồn:** [`src/qos_anomaly/data/loader.py`](../src/qos_anomaly/data/loader.py) — `validate_log_schema()`

```python
missing = [column for column in LOG_COLUMNS if column not in df.columns]
if missing:
    raise ValueError(f"Thiếu cột bắt buộc: {missing}")

if require_labels:
    missing_labels = [column for column in LABEL_COLUMNS if column not in df.columns]
    if missing_labels:
        raise ValueError(f"Thiếu cột nhãn: {missing_labels}")
```

Predict chỉ cần `LOG_COLUMNS`. Train/evaluate gọi `require_labels=True`, vì cần `is_anomaly` và `anomaly_type` để hiệu chỉnh/đánh giá.

### 25.4 Parse và loại dòng lỗi

**Nguồn:** [`src/qos_anomaly/data/loader.py`](../src/qos_anomaly/data/loader.py) — `clean_logs()`

```python
out["timestamp"] = pd.to_datetime(
    out["timestamp"], format="ISO8601", errors="coerce"
)
out["response_time_ms"] = pd.to_numeric(
    out["response_time_ms"], errors="coerce"
)
out["status_code"] = pd.to_numeric(out["status_code"], errors="coerce")
out["bytes_sent"] = pd.to_numeric(out["bytes_sent"], errors="coerce")

out = out.dropna(
    subset=["timestamp", "response_time_ms", "status_code", "bytes_sent"]
)
```

`errors="coerce"` không làm app crash ngay khi gặp chuỗi sai; nó đổi lỗi thành `NaT`/`NaN`. `dropna()` loại dòng đó. App so số dòng trước/sau để hiển thị số dòng bị loại.

### 25.5 Tính request rate

**Nguồn:** [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) — `FeatureBuilder._compute_request_rate()`

```python
window = pd.Timedelta(seconds=self.rate_window_seconds)
for _, group in df.groupby("client_ip", sort=False):
    timestamps = group["timestamp"].sort_values()
    for index in timestamps.index:
        current = timestamps.loc[index]
        start = current - window
        rates.loc[index] = float(
            ((timestamps >= start) & (timestamps <= current)).sum()
        )
```

Mỗi log nhìn ngược 60 giây, không nhìn request tương lai. Group theo IP bảo đảm request IP khác không bị đếm chung.

### 25.6 Học thống kê chỉ từ train

**Nguồn:** [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) — `FeatureBuilder.fit()`

```python
endpoint_counts = work["endpoint_uri"].value_counts(normalize=True)
self.endpoint_freq_map_ = endpoint_counts.to_dict()

work["is_error"] = (work["status_code"] >= 400).astype(int)
ip_stats = work.groupby("client_ip").agg(
    error_rate=("is_error", "mean"),
    avg_latency=("response_time_ms", "mean"),
)
self.ip_error_rate_map_ = ip_stats["error_rate"].to_dict()
self.ip_avg_latency_map_ = ip_stats["avg_latency"].to_dict()
```

`fit()` được gọi bằng `train_df`, không gọi bằng toàn dataset. Nếu fit trên test, statistics test lọt vào model input và metric bị data leakage.

### 25.7 Tạo 14 feature

**Nguồn:** [`src/qos_anomaly/data/features.py`](../src/qos_anomaly/data/features.py) — `FeatureBuilder.transform()`

```python
features["response_time_log1p"] = np.log1p(
    work["response_time_ms"].clip(lower=0)
)
features["status_class"] = (work["status_code"] // 100).astype(float)
features["is_5xx"] = (work["status_code"] >= 500).astype(float)
features["is_4xx"] = (
    (work["status_code"] >= 400) & (work["status_code"] < 500)
).astype(float)
features["request_rate"] = self._compute_request_rate(work)
features = features.join(self._time_features(work))
features["endpoint_freq"] = (
    work["endpoint_uri"].map(self.endpoint_freq_map_).fillna(0.0)
)
features["method_code"] = (
    work["http_method"].map(METHOD_CODES).fillna(-1).astype(float)
)
```

Phần cuối bắt đúng thứ tự feature:

```python
features = features[FEATURE_COLUMNS]
return features.astype(float)
```

Thứ tự rất quan trọng. Model tree hiểu cột theo vị trí array, không theo tên sau khi DataFrame chuyển thành `.values`.

### 25.8 Chia dữ liệu theo thời gian

**Nguồn:** [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) — `chronological_split()`

```python
n = len(df)
train_end = int(n * train_ratio)
val_end = int(n * (train_ratio + val_ratio))
train = df.iloc[:train_end].copy()
validation = df.iloc[train_end:val_end].copy()
test = df.iloc[val_end:].copy()
```

`load_logs()` đã sort timestamp. Vì vậy `iloc` đầu là log sớm, cuối là log muộn.

### 25.9 Khởi tạo và fit Isolation Forest

**Nguồn:** [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) — `train_isolation_forest()`

```python
model = IsolationForest(
    n_estimators=300,
    contamination=0.08,
    max_features=1.0,
    max_samples="auto",
    random_state=42,
    n_jobs=-1,
)
model.fit(X_train)
```

Không có `y_train` trong `fit()`. Đây là bằng chứng trực tiếp model được fit không giám sát. `n_jobs=-1` cho phép sklearn dùng các CPU core khả dụng khi công việc hỗ trợ parallel.

### 25.10 Đảo chiều score

**Nguồn:** [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) — `anomaly_scores()`

```python
def anomaly_scores(model: IsolationForest, X: np.ndarray) -> np.ndarray:
    return -model.decision_function(X)
```

Sklearn dùng score âm hơn cho outlier. Project đảo dấu để thống nhất UI: cao hơn là bất thường hơn.

### 25.11 Chọn threshold theo F1

**Nguồn:** [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) — `find_best_threshold()`

```python
low = float(np.percentile(scores, 1))
high = float(np.percentile(scores, 99))
thresholds = np.linspace(low, high, 200)

for threshold in thresholds:
    predicted = (scores >= threshold).astype(int)
    f1 = f1_score(y_true, predicted, zero_division=0)
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = float(threshold)
```

Đây là bước dùng nhãn validation. Nó không làm thay đổi 300 cây đã fit; nó chỉ tìm đường cắt trên score.

### 25.12 Bundle được tạo và lưu

**Nguồn:** [`src/qos_anomaly/model/train.py`](../src/qos_anomaly/model/train.py) — `train_pipeline()`

```python
bundle = {
    "model": model,
    "feature_builder": feature_builder.to_dict(),
    "feature_columns": FEATURE_COLUMNS,
    "threshold": threshold,
    "best_params": best_params,
    "metrics_val": {"f1": val_f1},
    "metrics_test_preview": {"f1": test_f1},
    "trained_at": trained_at,
    "sklearn_version": sklearn.__version__,
}
joblib.dump(bundle, output_path)
```

Một file giữ model và preprocessing statistics. App chỉ cần load một bundle, không cần fit feature maps lại.

### 25.13 Predict batch

**Nguồn:** [`src/qos_anomaly/model/predict.py`](../src/qos_anomaly/model/predict.py) — `predict_dataframe()`

```python
work = clean_logs(df)
feature_builder = FeatureBuilder.from_dict(bundle["feature_builder"])
X = feature_builder.transform(work).values
scores = anomaly_scores(bundle["model"], X)
threshold = bundle["threshold"]
is_anomaly = (scores >= threshold).astype(int)
```

Sau đó code copy log sạch và thêm output:

```python
result["anomaly_score"] = scores
result["is_anomaly_pred"] = is_anomaly
result["predicted_anomaly"] = is_anomaly.astype(bool)
```

`predicted_anomaly` và `is_anomaly_pred` cùng nghĩa; một cột dạng boolean, một cột dạng số 0/1.

### 25.14 Tính metric test

**Nguồn:** [`src/qos_anomaly/model/evaluate.py`](../src/qos_anomaly/model/evaluate.py) — `evaluate_model()`

```python
predicted = (scores >= bundle["threshold"]).astype(int)
actual = test_df["is_anomaly"].to_numpy(dtype=int)
tn, fp, fn, tp = confusion_matrix(
    actual, predicted, labels=[0, 1]
).ravel()
```

Sau đó từng metric dùng function chuẩn của sklearn:

```python
precision_score(actual, predicted)
recall_score(actual, predicted)
f1_score(actual, predicted)
accuracy_score(actual, predicted)
```

### 25.15 Cache model trong Streamlit

**Nguồn:** [`app/streamlit_app.py`](../app/streamlit_app.py) — `get_bundle()`

```python
@st.cache_resource
def get_bundle() -> dict:
    return load_bundle(MODEL_BUNDLE_PATH)
```

Nếu bỏ cache, mỗi lần user đổi checkbox/threshold Streamlit rerun file và đọc model lại từ disk. Cache giữ cùng resource model trong process.

### 25.16 Nút chạy và lưu DB

**Nguồn:** [`app/streamlit_app.py`](../app/streamlit_app.py) — khối nút Detection

```python
if st.button("Chạy Isolation Forest", type="primary"):
    result = predict_dataframe(input_df, bundle, threshold)
    if save_to_db:
        try:
            saved = save_results(result)
            st.success(f"Đã lưu {saved} dòng vào PostgreSQL.")
        except Exception as error:
            st.error(f"Không lưu được PostgreSQL: {error}")
    st.session_state["result"] = result
```

Predict chạy trước DB. Vì vậy lỗi DB không xóa kết quả model; `result` vẫn được đưa vào session state và hiển thị.

### 25.17 Parameterized SQL và transaction

**Nguồn:** [`src/qos_anomaly/db/repository.py`](../src/qos_anomaly/db/repository.py) — `save_results()`

```python
statement = text("""
    INSERT INTO detection_results
    (timestamp, client_ip, endpoint_uri, response_time_ms, status_code,
     anomaly_score, is_anomaly, predicted_at)
    VALUES
    (:timestamp, :client_ip, :endpoint_uri, :response_time_ms, :status_code,
     :anomaly_score, :is_anomaly, :predicted_at)
""")

with create_engine(url).begin() as connection:
    connection.execute(statement, rows)
```

Các token `:client_ip`, `:endpoint_uri` là bind parameter. SQLAlchemy/psycopg2 gửi value riêng với câu SQL, không ghép chuỗi user input. `begin()` bảo đảm commit toàn batch hoặc rollback khi lỗi.

### 25.18 Đọc lịch sử PostgreSQL

**Nguồn:** [`src/qos_anomaly/db/repository.py`](../src/qos_anomaly/db/repository.py) — `load_recent_results()`

```python
statement = text("""
    SELECT id, timestamp, client_ip, endpoint_uri, response_time_ms,
           status_code, anomaly_score, is_anomaly, predicted_at
    FROM detection_results
    ORDER BY predicted_at DESC, id DESC
    LIMIT :limit
""")
with create_engine(url).connect() as connection:
    return pd.read_sql(statement, connection, params={"limit": limit})
```

`LIMIT :limit` cũng là bind parameter. Tab **Lịch sử SQL** gọi hàm này khi bấm `Tải lịch sử từ SQL`.

### 25.19 Schema PostgreSQL

**Nguồn:** [`sql/schema.sql`](../sql/schema.sql)

```sql
CREATE TABLE IF NOT EXISTS detection_results (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    endpoint_uri VARCHAR(512) NOT NULL,
    response_time_ms DOUBLE PRECISION NOT NULL,
    status_code INTEGER NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`TIMESTAMPTZ` giữ timestamp có timezone. `BIGSERIAL` tự sinh ID. `NOT NULL` ngăn lưu record thiếu field cốt lõi.

### 25.20 PostgreSQL Docker

**Nguồn:** [`docker-compose.yml`](../docker-compose.yml)

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: qos_anomaly
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
    volumes:
      - qos_pg_data:/var/lib/postgresql/data
      - ./sql/schema.sql:/docker-entrypoint-initdb.d/01_schema.sql:ro
```

Volume `qos_pg_data` giữ data qua lần restart. Mount `schema.sql` chỉ tự chạy khi data directory còn rỗng.

## 26. Tài liệu tham khảo

1. Liu, Ting, Zhou. *Isolation Forest*. IEEE ICDM 2008. DOI: https://doi.org/10.1109/ICDM.2008.17
2. Liu, Ting, Zhou. *Isolation-based Anomaly Detection*. ACM TKDD 2012. DOI: https://doi.org/10.1145/2133360.2133363
3. scikit-learn IsolationForest: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
4. scikit-learn Outlier Detection: https://scikit-learn.org/stable/modules/outlier_detection.html
5. scikit-learn metric evaluation: https://scikit-learn.org/stable/modules/model_evaluation.html
6. RFC 9110 HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110
7. PostgreSQL documentation: https://www.postgresql.org/docs/
8. Streamlit documentation: https://docs.streamlit.io/
