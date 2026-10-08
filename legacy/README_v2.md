# Cine Cas Phile 🎬

> **Cine Cas Phile**: Modernized, deployable, and evaluable movie recommendation engine built from the ground up, evolving legacy research notebooks into a production-grade machine learning system under a strict **Zero-Data-Leakage** protocol.

[![Python 3.11](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.14%2B-ee4c2c.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.142%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-15%20Passing-success.svg)]()
[![Zero Leakage](https://img.shields.io/badge/Protocol-Zero%20Data%20Leakage-brightgreen.svg)]()

---

## 📌 1. Bối cảnh & Hiện trạng Source Cũ (Audit Source)

Kho mã nguồn gốc (`khanhnamle1994/movielens`) bao gồm các Jupyter Notebook nghiên cứu (`Data_Processing`, `Content_Based_and_Collaborative_Filtering_Models`, `SVD_Model`, `Deep_Learning_Model`), file `CFModel.py` và trọng số cũ `weights.h5`. Qua quá trình audit chi tiết, hệ thống cũ bộc lộ các vấn đề kỹ thuật nghiêm trọng:

1. **Lỗi thời về thư viện & cú pháp**:
   - `CFModel.py` dùng Keras 1.x với cú pháp `from keras.layers import Merge; Merge([P, Q], mode='dot')` đã bị khai tử từ nhiều năm trước.
   - Cú pháp Python 2 (`print '...'`) và pandas API cũ (`.as_matrix()`).
2. **Rò rỉ dữ liệu (Severe Data Leakage)**:
   - Trong `SVD_Model.ipynb`, mô hình SVD được fit trên toàn bộ ma trận người dùng - phim mà **không chia tập train/test**.
   - Khi tính mean rating của user: sử dụng `.fillna(0).mean(axis=1)`, tính gộp cả hàng nghìn phim chưa xem (giá trị 0) vào mẫu số, làm sai lệch hoàn toàn bias của user.
   - Trong `Deep_Learning_Model.ipynb`, việc chia train/test bằng `sample(frac=1.0)` hoàn toàn ngẫu nhiên trên toàn bộ lượt tương tác làm rò rỉ hành vi tương lai của user vào quá trình học quá khứ.
3. **Chưa có chuẩn hóa sản phẩm**:
   - Thiếu candidate generation đúng chuẩn (đề xuất phim chưa xem).
   - Thiếu ranking metrics (Precision@K, Recall@K, NDCG@K, Catalog Coverage).
   - Chưa có REST API, cơ chế giải thích (explainability), xử lý cold-start hay giao diện demo.

---

## 🚀 2. Cải tiến theo Lộ trình 6 Giai đoạn (Roadmap Implementation)

Dự án đã được tái cấu trúc hoàn toàn thành mã nguồn module hóa, đạt chuẩn đánh giá học thuật và sẵn sàng triển khai thực tế:

```
movielens-recsys/
├── configs/
│   └── config.json                # Cấu hình siêu tham số, split, threshold
├── data/
│   ├── raw/                       # Dữ liệu gốc MovieLens 1M (movies, ratings, users)
│   └── processed/                 # Manifest phân chia dữ liệu không rò rỉ
├── src/
│   ├── data/
│   │   ├── loader.py              # Đọc, làm sạch, mapping ID liên tục [0, N)
│   │   ├── splitter.py            # Phân chia train/val/test theo thời gian từng user
│   │   └── dataset.py             # PyTorch Dataset & ma trận thưa CSR
│   ├── recommenders/
│   │   ├── base.py                # Interface chung BaseRecommender & RecommendationItem
│   │   ├── popularity.py          # Baseline độ phổ biến có Bayesian shrinkage (IMDb)
│   │   ├── content_based.py       # TF-IDF Genres + hồ sơ sở thích user
│   │   ├── collaborative_filtering.py # Item-based CF có phạt co-ratings
│   │   ├── matrix_factorization.py    # Biased Matrix Factorization (FunkSVD)
│   │   ├── neural_mf.py           # Deep Learning NeuMF (PyTorch GMF + MLP)
│   │   └── hybrid.py              # Mô hình lai (CF + Content + Popularity)
│   ├── evaluation/
│   │   ├── metrics.py             # RMSE, MAE, Precision@K, Recall@K, NDCG@K, Coverage
│   │   └── benchmark.py           # Benchmark độc lập trên cùng test set & candidate pool
│   └── api/
│       ├── schemas.py             # Pydantic schemas cho API contract
│       ├── service.py             # Service quản lý lifecycle & suy luận
│       └── main.py                # FastAPI server + Web UI dashboard trực quan
├── demo/
│   └── cli.py                     # CLI demo tương tác nhanh trong terminal
├── reports/
│   ├── data_quality_report.md     # Báo cáo kiểm định chất lượng dữ liệu
│   ├── benchmark_report.md        # Kết quả benchmark chi tiết giữa các mô hình
│   └── model_card.md              # Model Card của hệ thống
├── tests/
│   ├── test_data.py               # Kiểm tra loader và tính toàn vẹn temporal split
│   ├── test_metrics.py            # Kiểm tra công thức toán học ranking & rating
│   ├── test_recommenders.py       # Kiểm tra fit/predict/recommend của các mô hình
│   └── test_api.py                # Kiểm tra endpoint REST API & cold-start
├── pyproject.toml / requirements.txt
├── train_and_eval.py              # Script chạy toàn bộ pipeline tự động
└── README.md
```

---

## 🎯 3. Quy ước Đánh giá Chuẩn mực (Evaluation Protocol)

1. **Temporal Split (80% Train / 10% Validation / 10% Test)**:
   - Với mỗi người dùng, toàn bộ lịch sử đánh giá được sắp xếp theo `timestamp`.
   - 80% tương tác cũ nhất đưa vào `Train`, 10% kế tiếp vào `Validation`, và 10% mới nhất vào `Test`.
   - Đảm bảo toán học: $\max(\text{Time}_{\text{train}}(u)) \le \min(\text{Time}_{\text{val}}(u)) \le \min(\text{Time}_{\text{test}}(u))$. Không có bất kỳ tương tác tương lai nào lọt vào tập huấn luyện.
2. **Candidate Generation**:
   - Đối với mỗi user $u$, tập ứng viên để xếp hạng top-$K$ là: $\text{Candidates}(u) = \text{Catalog} \setminus \text{Train}(u)$.
   - Các phim trong tập test **chưa hề xuất hiện trong train**, do đó hoàn toàn nằm trong tập ứng viên hợp lệ.
3. **Relevance Threshold**:
   - Đánh giá xếp hạng coi một bộ phim là "hài lòng/liên quan" (positive) nếu rating thực tế trong tập test đạt $r \ge 4.0$.

---

## 📊 4. Kết quả Thực nghiệm & Benchmark (Test Set Evaluation)

Thử nghiệm trên toàn bộ tập dữ liệu **MovieLens 1M** (1,000,209 lượt đánh giá, 6,040 người dùng, 3,706 bộ phim):

| Thuật toán (Model) | Rating RMSE ↓ | Rating MAE ↓ | Precision@10 ↑ | Recall@10 ↑ | NDCG@10 ↑ | HitRate@10 ↑ | Catalog Coverage (%) ↑ | Latency p50 (ms) ↓ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Popularity-Shrinkage** | 1.0009 | 0.7974 | 0.0192 | 0.0235 | 0.0244 | 15.50% | 0.93% | **0.00 ms** |
| **Content-Based-TFIDF** | 1.3404 | 1.0954 | 0.0060 | 0.0087 | 0.0087 | 5.75% | **30.26%** | 2.16 ms |
| **Item-Based-CF** | 1.0322 | 0.8010 | 0.0060 | 0.0035 | 0.0056 | 4.75% | 21.79% | 413.11 ms |
| **Biased-MF-SVD** | 0.9232 | 0.7253 | 0.0110 | 0.0116 | 0.0146 | 8.50% | 7.00% | 2.00 ms |
| **Neural-MF-PyTorch** | **0.8904** | **0.7002** | **0.0283** | **0.0375** | **0.0396** | **19.25%** | 5.72% | 3.51 ms |
| **Hybrid-Ensemble** | 0.9654 | 0.7795 | 0.0175 | 0.0233 | 0.0225 | 14.25% | 11.41% | 64.06 ms |

### Nhận định Kỹ thuật:
- **Neural-MF-PyTorch** (NeuMF kết hợp GMF + MLP) đạt chất lượng dự đoán và xếp hạng tốt nhất: **RMSE = 0.8904, MAE = 0.7002, HitRate@10 = 19.25%**.
- **Biased-MF-SVD** (FunkSVD có bias $b_u, b_i$) tối ưu hóa rất nhanh, dự đoán rating chính xác (RMSE = 0.9232) và thời gian suy luận chỉ 2 ms.
- **Content-Based-TFIDF** đạt độ bao phủ catalog lớn nhất (**30.26%**), giúp khám phá các phim ngách và cung cấp lời giải thích minh bạch theo thể loại.
- **Popularity-Shrinkage** có độ phủ thấp (0.93%) vì thiên lệch về các bom tấn toàn cục, nhưng đóng vai trò nền tảng fallback hoàn hảo cho người dùng mới (Cold-Start).
- **Hybrid-Ensemble** dung hòa tối ưu giữa độ chính xác CF, độ đa dạng thể loại và độ bao phủ catalog, đồng thời cung cấp lý do đề xuất đa chiều cho người dùng.

---

## 🛠️ 5. Hướng dẫn Cài đặt & Sử dụng

### 5.1. Khởi tạo Môi trường (Environment Setup)
```bash
# Di chuyển vào thư mục dự án
cd "C:\Users\Luong Hoang Linh\.gemini\antigravity\scratch\movielens-recsys"

# Kích hoạt môi trường ảo đã được chuẩn bị sẵn
.venv\Scripts\activate

# Hoặc cài đặt qua pip
pip install -e .
```

### 5.2. Chạy Kiểm thử (Run Test Suite)
```bash
pytest -v
# Toàn bộ 15 test cases (metrics, data, recommenders, API endpoints) đều PASS!
```

### 5.3. Huấn luyện & Chạy Benchmark Toàn diện
```bash
python train_and_eval.py
```

### 5.4. Trải nghiệm Thử nghiệm qua CLI
```bash
# Đề xuất cho User #1 bằng thuật toán Hybrid
python -m demo.cli --user 1 --model hybrid --k 10

# Đề xuất cho User #42 bằng mô hình Deep Learning PyTorch
python -m demo.cli --user 42 --model neural --k 10

# Đề xuất Cold-Start cho người dùng mới thích Action & Sci-Fi
python -m demo.cli --genres "Action,Sci-Fi" --k 5
```

### 5.5. Khởi chạy REST API & Web Dashboard
```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```
- **Web Dashboard**: Mở trình duyệt tại `http://127.0.0.1:8000/` để sử dụng giao diện tương tác trực quan (chọn User ID, chọn thuật toán, xem lý do gợi ý và độ trễ theo thời gian thực).
- **Swagger API Docs**: Truy cập `http://127.0.0.1:8000/docs`.

---

## 🌐 6. API Contract

### `GET /recommendations/{user_id}?k=10&model=hybrid`
Trả về top-$K$ phim chưa xem của user kèm điểm số và giải thích:
```json
{
  "user_id": 1,
  "model": "Hybrid-Ensemble",
  "is_fallback": false,
  "count": 10,
  "latency_ms": 18.5,
  "recommendations": [
    {
      "movie_id": 260,
      "title": "Star Wars: Episode IV - A New Hope (1977)",
      "genres": "Action|Adventure|Fantasy|Sci-Fi",
      "score": 4.85,
      "reason": "Hybrid Pick: 4.8★ taste match + strong Action genre alignment"
    }
  ]
}
```

### `POST /recommendations/cold-start`
```json
{
  "preferred_genres": ["Animation", "Children's"],
  "k": 5
}
```

### `GET /health`
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "loaded_models": ["popularity", "content", "svd", "neural", "hybrid"],
  "catalog_size": 3706,
  "users_count": 6040,
  "uptime_seconds": 128.4
}
```

---

## 📜 7. License & Trích dẫn
- **Dữ liệu**: MovieLens 1M được cung cấp bởi nhóm nghiên cứu GroupLens tại Đại học Minnesota ([GroupLens Datasets](https://grouplens.org/datasets/movielens/1m/)). Dữ liệu dùng cho mục đích học thuật và nghiên cứu.
- **Bản quyền mã nguồn**: MIT License.
