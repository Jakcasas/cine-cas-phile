# Cine (cas) phile.

Phiên bản **1.0**.

Câu lạc bộ khám phá phim với gợi ý có giải thích, giao diện tiếng Việt mang tinh thần tuyển chọn của MUBI, tông **đỏ rượu vang / trắng ngà / ánh sáng hổ phách**. Project chạy cục bộ, có dữ liệu MovieLens bạn cung cấp và mô hình đã huấn luyện; không cần API key.

## Chạy ngay trên Windows

**Web đã chạy trên Netlify:** https://cinecasphile.netlify.app. **GitHub:** https://github.com/Jakcasas/cine-cas-phile (public). Địa chỉ chính thức: **https://cinecasphile.netlify.app/**. Hướng dẫn dựng/deploy: [docs/DOMAIN.md](docs/DOMAIN.md).

Nhấp đúp **Start-CineCasPhile.cmd**, sau đó mở **http://127.0.0.1:8000**. Lần đầu cần Python 3.11 trở lên và Internet để cài thư viện. Máy chủ đọc artifact đã lưu, không huấn luyện neural mỗi lần mở. Dừng bằng `Ctrl+C`.

Hoặc chạy thủ công trong thư mục project:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.cli serve
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.cli serve
```

## Mở trong Visual Studio Code / Visual Studio

Trên Windows, mở thư mục project trong **Visual Studio Code** bằng `code .` hoặc dùng **File → Open Folder**. Chọn môi trường Python `.venv` nếu editor hỏi. Nhấn **F5** với cấu hình **“Cine (cas) phile. 1.0 — website”** để chuẩn bị môi trường và chạy server tại `http://127.0.0.1:8000`. Dừng server bằng nút Stop trong editor. Mục **Terminal → Run Task** có lệnh kiểm thử Python, đối chiếu thuật toán Python/Netlify và build website. Để chạy hai lệnh kiểm thử, cài thư viện phát triển bằng `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`; để build website, chạy `npm ci` một lần.

Nếu dùng **Visual Studio** bản đầy đủ, hãy mở cùng thư mục bằng **File → Open → Folder**, cài workload Python development, chọn interpreter `.venv\Scripts\python.exe`, rồi chạy `python -m src.cli serve`. Cấu hình `.vscode/` dành riêng cho Visual Studio Code.

`requirements.lock.txt` ghi lại các phiên bản đã dùng để kiểm thử trên Python 3.12 / Windows. `requirements.txt` là các khoảng phiên bản hỗ trợ. Thư mục `web/` phải nằm cạnh `src/`; đây là một project chạy từ source, không phải wheel chứa toàn bộ dữ liệu.

## Trải nghiệm

- **Khám phá:** tìm tên phim, lọc một trong 18 thể loại, lọc thời kỳ, sắp xếp và phân trang.
- **Dành cho bạn:** chọn gu phim, chấm sao một vài phim; hệ thống gợi ý phim chưa đánh giá. Điều chỉnh độ khám phá để MMR cân bằng điểm phù hợp và đa dạng thể loại.
- **Chi tiết phim:** điểm cộng đồng trong train, điểm Bayesian, chấm/xóa đánh giá, phim tương tự và nút “Tìm phim cùng gu”.
- **Danh sách xem / Đã đánh giá:** bản cục bộ lưu SQLite; bản Netlify lưu trong localStorage của từng trình duyệt, không đồng bộ thiết bị.
- **Dữ liệu:** thống kê thật, cách chia dữ liệu và benchmark Python. Bản Netlify chuyển cùng artifact sang JavaScript; 10 trường hợp đối chiếu cả 5 model cho cùng thứ tự gợi ý.

Hồ sơ cá nhân bắt đầu **trống**, không tự mượn lịch sử của user 1. Ô “MovieLens user” là tùy chọn để thử các người dùng của bộ dữ liệu. Đánh giá cá nhân cập nhật Content và Item-CF ngay; SVD dùng lịch sử train của ID MovieLens và cần huấn luyện lại để thay đổi nhân tố ẩn.

Slogan: **One film, one fish fillet. (Un film, un filet de poisson.)** Giao diện dùng Noto Serif có đầy đủ dấu tiếng Việt; slogan giữ Mirella gốc; logo giữ Operation Napalm và tên thương hiệu góc trái giữ font cũ. Chữ có khoảng cách tự nhiên, không ngắt dòng cứng. Menu không có mục riêng MUBI/Letterboxd; các phim nhập nằm trong kho chung.

Poster được lấy theo nguồn có đối chiếu phim: **1,045 phim có URL ảnh**, gồm 829 phim có poster Letterboxd, 35 từ MUBI; hai website FshareTV và PhimMoi có 1.011 phim khớp trên 3.883 phim gốc. Hero hiện dùng cảnh trong *In the Mood for Love* do bạn cung cấp. Hai thẻ bộ sưu tập lần lượt dùng ảnh từ *2001: A Space Odyssey* và *Love Letter* bạn cung cấp. Ảnh *Love Letter* được AI hỗ trợ tăng độ phân giải; thẻ ghi nguồn phim và đạo diễn. Artwork phụ chỉ dùng khung 2, 3, 4 đã chọn. Khi không có ảnh hoặc CDN lỗi, thẻ dùng bìa minh họa có tên phim. Không phát phim.

**Đánh giá đa nguồn:** mở chi tiết phim để xem Letterboxd/IMDb (khán giả), Rotten Tomatoes (Tomatometer/Popcornmeter), Metacritic (Metascore/khán giả) và MUBI khi có. Giữ riêng thang điểm và ngày kiểm tra; trường thiếu dữ liệu hiển thị rõ, không tự bịa điểm. IMDb là snapshot qua FshareTV; RT/Metacritic hiện chỉ có một nhóm phim đã xác minh.

**Tìm bằng ảnh:** chọn ảnh cảnh phim JPEG/PNG/WebP dưới 8 MB. CLIP ONNX chạy trên CPU, đối chiếu cảnh thật và poster trong kho tham chiếu. Ảnh nhập xử lý cục bộ, không lưu và không gửi Google hay nhà cung cấp khác. Cảnh chưa có trong kho có thể trả về phim gần giống thay vì nhận diện đúng. Chi tiết nguồn, giấy phép và lệnh cập nhật: [docs/ENRICHMENT.md](docs/ENRICHMENT.md).

## Thuật toán

| Chế độ | Cách tính | Cold start |
|---|---|---|
| Popularity | Bayesian average, prior 25 lượt đánh giá | Gợi ý từ cộng đồng |
| Content | TF-IDF thể loại nguyên vẹn, trọng số `max(r−3,0)`, half-life 180 ngày trong train | Thể loại / phim làm nguồn cảm hứng |
| Collaborative | Item-based adjusted cosine, co-rating shrinkage 15, giữ 60 láng giềng dương | Điểm cộng đồng khi không có lịch sử |
| SVD | Truncated SVD của phần dư baseline, 32 nhân tố; seed 42 | Bayesian khi thiếu ID MovieLens |
| Hybrid | Min-max từng tín hiệu, trọng số CF .35 / SVD .25 / Content .25 / Pop .15; bỏ tín hiệu không khả dụng rồi chuẩn hóa lại | Thể loại + cộng đồng |

MMR chọn lại trong tối đa `max(200, 5K)` ứng viên đầu tiên, dùng cosine TF-IDF giữa phim để giảm trùng thể loại. “Độ khám phá” không đảm bảo mọi thể loại đều xuất hiện. Điểm trên thẻ là **điểm xếp hạng tương đối**, không phải xác suất bạn sẽ thích phim; điểm cộng đồng `/5` được hiển thị riêng.

Engine phục vụ dùng NumPy/SciPy, vector hóa suy luận và dùng chung các đặc trưng. Artifact `.npz` được đọc với `allow_pickle=False`, kiểm tra SHA-256 của dữ liệu và phiên bản định dạng. Các thuật toán SGD MF / NeuMF của bản trước vẫn còn để tham khảo; PyTorch là extra tùy chọn và **không nằm trong 5 chế độ của ứng dụng mới**.

## Huấn luyện, đánh giá và CLI

```powershell
.\.venv\Scripts\python.exe -m src.cli train
.\.venv\Scripts\python.exe -m src.cli benchmark --users 200 --rating-pairs 10000
.\.venv\Scripts\python.exe -m src.cli recommend --user 1 --model svd --k 10
.\.venv\Scripts\python.exe -m src.cli recommend --genres "Action,Sci-Fi"
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=runtime/test-run
```

Train tạo `artifacts/engine.npz`, `data/processed/split_manifest.json` và `reports/data_quality.json`. Benchmark tạo `reports/benchmark.json` và `reports/benchmark_report.md`. File `Cine_Cas_Phile_AllInOne.py` là launcher tương thích cho `--serve`, `--train`, `--benchmark`, `--recommend` và `--cold-start`; bản all-in-one gốc được giữ trong `legacy/`.

Chia thời gian **theo từng người dùng**, gần tỷ lệ 80/10/10; các nhóm timestamp bằng nhau không bị tách. Kiểm tra cả train→validation, validation→test, train→test và trùng cặp user/movie. Người dùng có lịch sử quá ngắn hoặc một timestamp được giữ trong train; người dùng chỉ có hai nhóm thời gian có thể không có validation.

Train thực tế: **799.898**; validation: **99.791**; test: **100.520** đánh giá. Catalog có **3,915** phim (3.883 MovieLens và 32 tác phẩm bổ sung); **3.706** phim có đánh giá trong dữ liệu; **6.040** người dùng; tổng **1.000.209** đánh giá. Các con số từ báo cáo đã chạy, không phải số liệu mô phỏng.

Benchmark dùng cùng tập ứng viên **toàn catalog trừ phim train và validation**, phim relevant có test rating ≥4, seed 42, K=10, MMR=0. Lấy mẫu 200 người có ít nhất một phim test relevant và 10.000 cặp test rating. RMSE/MAE chỉ áp dụng cho đầu ra dự đoán rating của Popularity, CF và SVD; Content/Hybrid chưa hiệu chỉnh rating nên không công bố RMSE/MAE cho chúng. Không tối ưu tham số trên test.

**Giới hạn kiểm định:** chia theo từng người dùng không tương đương chia theo một thời điểm toàn cục; metadata toàn catalog được giả định đã biết. Không tuyên bố “100% zero leakage” cho mọi kịch bản triển khai. SVD hiện đạt NDCG@10 cao hơn Hybrid trong benchmark kèm theo; Hybrid là lựa chọn phối hợp nhiều tín hiệu và hỗ trợ gu mới, không phải thuật toán luôn thắng. Coverage và latency phụ thuộc mẫu đánh giá và phần cứng.

## API và cấu trúc

OpenAPI: **http://127.0.0.1:8000/docs**.

| Endpoint | Chức năng |
|---|---|
| `GET /health`, `/stats`, `/models`, `/benchmark` | Trạng thái / dữ liệu / báo cáo |
| `GET /movies?q=&genre=&page=&sort=` | Catalog phân trang |
| `GET /movies/{movie_id}` | Chi tiết, poster, điểm đa nguồn và phim tương tự |
| `GET /visual-search/status`, `POST /visual-search` | Trạng thái và tìm phim bằng ảnh multipart |
| `POST /discover` | Gợi ý bằng profile, genres, seed_ids hoặc MovieLens user |
| `POST /profiles`, `GET /profiles/{id}` | Hồ sơ cục bộ |
| `PUT /profiles/{id}/preferences` | Lưu thể loại |
| `PUT/DELETE /profiles/{id}/ratings/{movie_id}` | Chấm/xóa sao |
| `PUT/DELETE /profiles/{id}/watchlist/{movie_id}` | Lưu/bỏ lưu phim |

```json
{"preferred_genres":["Sci-Fi","Drama"],"model":"hybrid","k":10,"diversity":0.2}
```

```text
src/cli.py                 Train / benchmark / serve / recommend
src/recommenders/engine.py Engine dùng chung và artifact
src/api/                   API, catalog service và SQLite profiles
src/data/                  CSV/TSV/DAT loader và temporal splitter
web/                       HTML/CSS/JS, ảnh gốc, không cần frontend build
data/raw/                  Dữ liệu người dùng cung cấp
artifacts/                 Mô hình train-only đã lưu
reports/                   Số liệu đánh giá thực
tests/                     Kiểm thử engine / data / API / persistence
legacy/                    Mã và tài liệu gốc để đối chiếu
docs/                      Kiến trúc, model card và thông tin nguồn
runtime/                   SQLite và dữ liệu chạy local (không đưa vào ZIP)
```

Đường dẫn mặc định dựa trên thư mục project. Có thể đặt `CINE_DATA_DIR` (chứa movies.csv, ratings.csv) và `CINE_DB_PATH`. Khi đổi dữ liệu, chạy lại train và benchmark; server từ chối artifact khác fingerprint. CSV MovieLens 1M của bạn dùng tab separator; loader cũng đọc CSV với movieId/userId và DAT không header.

## Phạm vi sử dụng và nguồn

Bản Python mặc định chỉ bind `127.0.0.1`; UUID hồ sơ cục bộ chưa có đăng nhập/phân quyền. Bản Netlify đã triển khai dùng API stateless và hồ sơ riêng trong trình duyệt, không công khai SQLite. Nếu cần tài khoản đồng bộ giữa các thiết bị, phải bổ sung đăng nhập và phân quyền cho hồ sơ trên máy chủ.

Nguồn: `Cine_Cas_Phile.zip`, bản Python all-in-one, `movielens-recsys.zip` và `movielens-master.zip` do bạn cung cấp. `legacy/` giữ bản gốc chưa được xác minh và có thể cần thư viện/đường dẫn cũ. Kiểu giao diện tham khảo MUBI; thương hiệu và ảnh của Cine (cas) phile. là riêng.

MovieLens thuộc GroupLens, University of Minnesota. Điều khoản gốc trong `docs/MOVIELENS_README.txt` yêu cầu ghi nhận nguồn, không phân phối lại hoặc dùng thương mại nếu chưa có quyền phù hợp. Repository được công khai theo yêu cầu của chủ project; giấy phép riêng của dữ liệu và tài nguyên vẫn được giữ nguyên. Giấy phép MIT của repository nguồn được giữ tại `docs/UPSTREAM_LICENSE.txt`.

Citation: F. Maxwell Harper and Joseph A. Konstan (2015), *The MovieLens Datasets: History and Context*, ACM TiiS 5(4), Article 19, DOI: 10.1145/2827872.
