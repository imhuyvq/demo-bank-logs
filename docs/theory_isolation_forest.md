# Lý thuyết Isolation Forest và Đánh giá Mô hình Không giám sát

## 1. Bài toán phát hiện bất thường

Trong hệ thống QoS, log truy cập ghi nhận hành vi người dùng và hệ thống. **Anomaly** là các mẫu khác biệt đáng kể so với phần lớn traffic bình thường, ví dụ:

- **Spam request:** một IP gửi burst request bất thường
- **High latency:** thời gian phản hồi cực cao
- **System error:** tần suất lỗi 5xx tăng đột biến

Học **không giám sát** không cần nhãn khi train; nhãn trong dataset mẫu chỉ dùng để **đánh giá** độ chính xác.

## 2. Isolation Forest (IF)

### 2.1 Ý tưởng

IF xây dựng nhiều cây quyết định ngẫu nhiên. Điểm **bất thường** thường ít và khác biệt → bị **cô lập (isolate)** sớm hơn → đường đi ngắn hơn trong cây.

### 2.2 Anomaly score

- Sklearn trả `decision_function`: giá trị âm hơn thường là outlier
- Module chuẩn hóa: `anomaly_score = -decision_function(X)` → **cao hơn = bất thường hơn**

### 2.3 Hyperparameters

| Tham số | Ý nghĩa |
|---------|---------|
| `n_estimators` | Số cây; tăng → ổn định hơn, chậm hơn |
| `contamination` | Tỷ lệ outlier kỳ vọng trong train |
| `max_features` | Số feature dùng mỗi lần split |

### 2.4 Ngưỡng (Threshold)

`contamination` gợi ý tỷ lệ anomaly, nhưng ngưỡng tốt nhất nên chọn bằng cách quét trên validation để tối đa **F1** (khi có nhãn giả lập).

## 3. Chỉ số đánh giá (có nhãn tham chiếu)

| Metric | Công thức / Ý nghĩa |
|--------|---------------------|
| **Precision** | TP / (TP + FP) — trong số cảnh báo, bao nhiêu đúng |
| **Recall** | TP / (TP + FN) — bắt được bao nhiêu anomaly thật |
| **F1-Score** | Trung bình điều hòa Precision và Recall |
| **FPR** | FP / (FP + TN) — tỷ lệ báo động giả |

## 4. Dataset mẫu offline

Do chưa có log production, project dùng **generator mô phỏng** tạo `train_logs_1000.csv` / `train_logs_1000.json` (~1000 dòng, ~8% anomaly, domain API ngân hàng). Dataset này phục vụ EDA, train và demo Streamlit.

## 5. Baseline so sánh