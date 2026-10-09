# Cine (cas) phile.

Phiên bản **1.0**.

Câu lạc bộ khám phá phim với gợi ý có giải thích, giao diện tiếng Việt mang tinh thần tuyển chọn của MUBI, tông **đỏ rượu vang / trắng ngà / ánh sáng hổ phách**. Website ưu tiên thể loại, thời kỳ, cảm xúc và phim khán giả yêu thích. Khách dùng ngay trên thiết bị; tài khoản, chat, blog và góp ý dùng MongoDB Atlas. Giữ version 1.0. Hướng dẫn cấu hình online: [docs/ONLINE_SETUP.md](docs/ONLINE_SETUP.md).

## Chạy ngay trên Windows

**Web đã chạy trên Netlify:** https://cinecasphile.netlify.app. **GitHub:** https://github.com/Jakcasas/cine-cas-phile (public). Địa chỉ chính thức: **https://cinecasphile.netlify.app/**. Hướng dẫn dựng/deploy: [docs/DOMAIN.md](docs/DOMAIN.md).

Nhấp đúp **Start-CineCasPhile.cmd**, sau đó mở **http://127.0.0.1:8001**. Cần Node.js 22 trở lên; lần đầu tự cài thư viện. Có thể mở thư mục trong VS Code và chọn F5 → **Cine (cas) phile. 1.0 — full website**.

```powershell
npm ci
npm run build
npm run dev
```

Bản thử dùng database `cinecasphile_dev` để tách khỏi dữ liệu cộng đồng trên website thật. Chế độ khách lưu trong trình duyệt khi không có MongoDB. API nghiên cứu Python vẫn chạy bằng `python -m src.cli serve` trên cổng 8000; chức năng cộng đồng đầy đủ chạy bằng launcher Node phía trên.

## Mở trong Visual Studio Code / Visual Studio

Mở thư mục bằng **File → Open Folder** hoặc `code .`. Chọn F5 → **Cine (cas) phile. 1.0 — full website** để build và chạy cổng 8001. Cấu hình Python riêng vẫn có cho API nghiên cứu. Terminal → Run Task có build website, kiểm tra MongoDB/tài khoản/cộng đồng và các kiểm tra Python.

Visual Studio bản đầy đủ có thể mở thư mục và chạy `npm run dev` trong terminal. Cấu hình `.vscode/` dành riêng cho Visual Studio Code.

`requirements.lock.txt` ghi lại các phiên bản đã dùng để kiểm thử trên Python 3.12 / Windows. `requirements.txt` là các khoảng phiên bản hỗ trợ. Thư mục `web/` phải nằm cạnh `src/`; đây là một project chạy từ source, không phải wheel chứa toàn bộ dữ liệu.

## Trải nghiệm

Chỉ có **4 mục chính**: Khám phá, Dành cho bạn, Danh sách xem, Bộ sưu tập.

- **Khảo sát gu phim:** thể loại yêu thích, thời kỳ, cảm xúc, phim gợi cảm hứng và thể loại muốn tránh; giải thích lý do gợi ý. Giao diện không yêu cầu chọn thuật toán hoặc ID MovieLens.
- **Bộ sưu tập:** đánh dấu đã xem, chấm 0,5–5 sao, lưu danh sách muốn xem và xuất JSON. Tìm kiếm giữ trong nhật ký; lọc đã/chưa chấm, sắp xếp sao cá nhân và xem tổng phim/sao. Khách có biệt danh hoặc tên Ẩn danh; tài khoản đồng bộ MongoDB.
- **Tìm kiếm:** tên Việt/tên gốc không cần dấu, đạo diễn, năm và mã IMDb; gợi ý tên gần đúng khi không có kết quả. Có nút bỏ bộ lọc. Lựa chọn yêu thích và muốn tránh mâu thuẫn được nhắc trước khi lưu khảo sát.
- **Lịch phim:** chọn Việt Nam, Mỹ, Anh, Pháp, Nhật Bản hoặc Hàn Quốc; lọc đã phát hành, mới công chiếu theo lịch (30 ngày), đang chiếu và sắp chiếu. Đợt đối chiếu 09/10/2026 ghép 98 phim với 180 mục lịch rạp, bổ sung 20 phim và poster. Nguồn rạp: Galaxy, Harkins, Everyman, Pathé, TOHO Cinemas và Megabox. Everyman đang chiếu được kiểm tra tại The Whiteley, London; các nguồn còn lại là danh sách của chuỗi. Đây là phạm vi rạp đã kiểm tra, không phải toàn bộ lịch chiếu quốc gia. Phim bán vé trước không được gán đang chiếu. Phim tái chiếu giữ năm gốc và không được tính là tác phẩm mới công chiếu. Cùng phim có thể mang trạng thái khác nhau ở mỗi nước, theo múi giờ thị trường; quốc gia phát hành không đồng nghĩa quốc gia sản xuất. IMDb bổ sung lịch phát hành. Phim chưa phát hành trong thị trường đang chọn được loại khỏi gợi ý mặc định. Trạng thái rạp hết hiệu lực sau 7 ngày; theo liên kết nguồn để kiểm tra suất thực tế. Xem [docs/CINEMA_LISTINGS.md](docs/CINEMA_LISTINGS.md).
- **Cộng đồng:** phòng chat cập nhật định kỳ, đánh giá theo phim, thích bài, nội dung spoiler được thu gọn, báo cáo và gỡ bài của mình.
- **Blog:** người dùng đăng công khai, theo lựa chọn mới nhất của chủ website; có báo cáo nội dung. Bản nháp tự lưu trên thiết bị. Không sao chép đánh giá của người dùng Letterboxd.
- **Tài khoản:** đăng ký email/mật khẩu, đăng nhập Google/Facebook khi đã cấu hình ứng dụng OAuth; session cookie HttpOnly, Secure, SameSite=Lax; mật khẩu scrypt; giới hạn tần suất và kiểm tra quyền trên server. Chế độ khách online có thể tham gia cộng đồng ẩn danh.
- **Góp ý:** trải nghiệm, ý tưởng và báo lỗi được lưu vào MongoDB. Không hiển thị số người dùng hoặc đánh giá cộng đồng giả.

Slogan: **One film, one fish fillet. (Un film, un filet de poisson.)** Giao diện dùng Noto Serif có đầy đủ dấu tiếng Việt; slogan giữ Mirella gốc; logo giữ Operation Napalm và tên thương hiệu góc trái giữ font cũ. Chữ có khoảng cách tự nhiên, không ngắt dòng cứng. Menu không có mục riêng MUBI/Letterboxd; các phim nhập nằm trong kho chung.

Poster được lấy theo nguồn có đối chiếu phim: Poster đã được bổ sung từ metadata công khai có đối chiếu tên/năm; báo cáo nằm ở `reports/viewer_catalog_sync.json` và `reports/poster_sync.json`. Catalog bổ sung Digger, Verity, Other Mommy, Clayface và Forgotten Island (2026). Các phim vẫn chưa tìm được poster được ghi trong báo cáo; không gán ảnh sai để lấp chỗ trống. Hero hiện dùng bản HD từ cảnh *In the Mood for Love* do bạn cung cấp. Hai thẻ bộ sưu tập lần lượt dùng ảnh từ *2001: A Space Odyssey* và *Love Letter* bạn cung cấp. Ảnh *Love Letter* được AI hỗ trợ tăng độ phân giải; thẻ ghi nguồn phim và đạo diễn. Artwork phụ chỉ dùng khung 2, 3, 4 đã chọn. Khi không có ảnh hoặc CDN lỗi, thẻ dùng bìa minh họa có tên phim. Không phát phim.

**Đánh giá đa nguồn:** mở chi tiết phim để xem Letterboxd/IMDb (khán giả), Rotten Tomatoes (Tomatometer/Popcornmeter), Metacritic (Metascore/khán giả) và MUBI khi có. Giữ riêng thang điểm và ngày kiểm tra; trường thiếu dữ liệu hiển thị rõ, không tự bịa điểm. IMDb là snapshot qua FshareTV; RT/Metacritic hiện chỉ có một nhóm phim đã xác minh.

**Tìm bằng ảnh:** chọn ảnh cảnh phim JPEG/PNG/WebP dưới 8 MB. CLIP ONNX chạy trên CPU, đối chiếu cảnh thật và poster trong kho tham chiếu. Ảnh nhập xử lý cục bộ, không lưu và không gửi Google hay nhà cung cấp khác. Cảnh chưa có trong kho có thể trả về phim gần giống thay vì nhận diện đúng. Chi tiết nguồn, giấy phép và lệnh cập nhật: [docs/ENRICHMENT.md](docs/ENRICHMENT.md).

## Engine nghiên cứu

Website dành cho khán giả dùng `/api/viewer-discover`: đối chiếu thể loại, thời kỳ, cảm xúc, phim yêu thích và điểm cộng đồng, bỏ phim đã xem hoặc thể loại muốn tránh. Các chế độ dưới đây được giữ cho CLI/API nghiên cứu; người xem không cần chọn thuật toán.

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

Train thực tế: **799.898**; validation: **99.791**; test: **100.520** đánh giá. Catalog có **4.064** phim (3.883 MovieLens và 181 tác phẩm bổ sung); **3.706** phim có đánh giá trong dữ liệu; **6.040** người dùng; tổng **1.000.209** đánh giá. Các con số từ báo cáo đã chạy, không phải số liệu mô phỏng.

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

Bản Python nghiên cứu mặc định chỉ bind `127.0.0.1`; UUID hồ sơ cục bộ chưa có đăng nhập/phân quyền. Bản Node/Netlify dùng tài khoản và phân quyền trên server, đồng bộ hồ sơ online qua MongoDB Atlas. Khách chưa đăng nhập lưu hồ sơ riêng trên thiết bị. SQLite local không được công khai trên website.

Nguồn: `Cine_Cas_Phile.zip`, bản Python all-in-one, `movielens-recsys.zip` và `movielens-master.zip` do bạn cung cấp. `legacy/` giữ bản gốc chưa được xác minh và có thể cần thư viện/đường dẫn cũ. Kiểu giao diện tham khảo MUBI; thương hiệu và ảnh của Cine (cas) phile. là riêng.

MovieLens thuộc GroupLens, University of Minnesota. Điều khoản gốc trong `docs/MOVIELENS_README.txt` yêu cầu ghi nhận nguồn, không phân phối lại hoặc dùng thương mại nếu chưa có quyền phù hợp. Repository được công khai theo yêu cầu của chủ project; giấy phép riêng của dữ liệu và tài nguyên vẫn được giữ nguyên. Giấy phép MIT của repository nguồn được giữ tại `docs/UPSTREAM_LICENSE.txt`.

Citation: F. Maxwell Harper and Joseph A. Konstan (2015), *The MovieLens Datasets: History and Context*, ACM TiiS 5(4), Article 19, DOI: 10.1145/2827872.
