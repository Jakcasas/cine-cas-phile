"""Update user documentation from completed source and model reports."""
from pathlib import Path
import json
from src import settings
from src.api.enrichment import MovieEnrichment
from src.data.catalog import load_catalog

root=settings.ROOT
catalog=load_catalog(settings.DATA_DIR);enrichment=MovieEnrichment(root/'data/enrichment/movie_images.json')
sources={name:sum(any(s['name']==name for s in entry['poster_sources']) for entry in enrichment.movies.values())
         for name in ['FshareTV','PhimMoi','MUBI','Letterboxd']}
posters=sum(bool(e['poster_sources']) for e in enrichment.movies.values())
path=root/'README.md';text=path.read_text(encoding='utf-8')
old='Ảnh hero là ảnh AI gốc. Bìa/thumbnails là minh họa điện ảnh, **không phải poster hoặc ảnh trích từ các phim có tên trên thẻ**. MovieLens 1M không có tóm tắt nội dung, đạo diễn, thời lượng hay poster; project không tự bịa các trường này và không phát phim.'
new=f'''Slogan: **One film, one fish fillet. (Un film, un filet de poisson.)** Giao diện dùng Mirella với bản bổ sung dấu tiếng Việt cho project cá nhân; logo giữ Operation Napalm và tên thương hiệu góc trái giữ font cũ. Chữ có khoảng cách tự nhiên, không ngắt dòng cứng. Menu không có mục riêng MUBI/Letterboxd; các phim nhập nằm trong kho chung.

Poster được lấy theo nguồn có đối chiếu phim: **{posters:,} phim có URL ảnh**, gồm {sources['Letterboxd']} phim có poster Letterboxd, {sources['MUBI']} từ MUBI; hai website FshareTV và PhimMoi có 1.011 phim khớp trên 3.883 phim gốc. Hero dùng artwork gốc và chỉ hiển thị các khung 2, 3, 4 bạn chọn. Khi không có ảnh hoặc CDN lỗi, thẻ dùng bìa minh họa có tên phim. Không phát phim.

**Đánh giá đa nguồn:** mở chi tiết phim để xem Letterboxd/IMDb (khán giả), Rotten Tomatoes (Tomatometer/Popcornmeter), Metacritic (Metascore/khán giả) và MUBI khi có. Giữ riêng thang điểm và ngày kiểm tra; trường thiếu dữ liệu hiển thị rõ, không tự bịa điểm. IMDb là snapshot qua FshareTV; RT/Metacritic hiện chỉ có một nhóm phim đã xác minh.

**Tìm bằng ảnh:** chọn ảnh cảnh phim JPEG/PNG/WebP dưới 8 MB. CLIP ONNX chạy trên CPU, đối chiếu cảnh thật và poster trong kho tham chiếu. Ảnh nhập xử lý cục bộ, không lưu và không gửi Google hay nhà cung cấp khác. Cảnh chưa có trong kho có thể trả về phim gần giống thay vì nhận diện đúng. Chi tiết nguồn, giấy phép và lệnh cập nhật: [docs/ENRICHMENT.md](docs/ENRICHMENT.md).'''
text=text.replace(old,new)
text=text.replace('Catalog có **3.883** phim;',f'Catalog có **{len(catalog):,}** phim (3.883 MovieLens và {len(catalog)-3883} tác phẩm bổ sung);')
text=text.replace('| `GET /movies/{movie_id}` | Chi tiết và phim tương tự |','| `GET /movies/{movie_id}` | Chi tiết, poster, điểm đa nguồn và phim tương tự |\n| `GET /visual-search/status`, `POST /visual-search` | Trạng thái và tìm phim bằng ảnh multipart |')
path.write_text(text,encoding='utf-8')
summary={'catalog_movies':len(catalog),'supplemental_movies':len(catalog)-3883,'movies_with_image_urls':posters,
         'poster_sources':sources,'ratings_sources':{provider:sum(any(r['provider']==provider for r in e['external_ratings']) for e in enrichment.movies.values()) for provider in ['Letterboxd','IMDb','Rotten Tomatoes','Metacritic','MUBI']}}
(root/'reports/release_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary),flush=True)
