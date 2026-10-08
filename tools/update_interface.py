"""Apply the editorial shelf and rating display to the existing interface."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'web/index.html';text=path.read_text(encoding='utf-8')
text=text.replace('<button class="nav" data-view="foryou">','<button class="nav" data-view="curated">MUBI & Letterboxd</button><button class="nav" data-view="foryou">',1)
text=text.replace('<option value="1990:2000">','<option value="2020:2026">2020–2026</option><option value="2010:2019">2010–2019</option><option value="2001:2009">2001–2009</option><option value="1990:2000">')
text=text.replace('Ảnh và bìa là minh họa. Không cung cấp phát phim.','Poster có liên kết nguồn; bìa minh họa khi thiếu ảnh. Không cung cấp phát phim.')
path.write_text(text,encoding='utf-8')
path=ROOT/'web/app.js';text=path.read_text(encoding='utf-8')
text=text.replace("const copy={discover:","const copy={curated:['THE EDITORIAL SHELF','Những góc nhìn điện ảnh khác.','Phim và poster từ MUBI, Letterboxd — gồm cả La Mesías và các tác phẩm mới.'],discover:")
text=text.replace("if(state.view!=='discover')setView('discover');else loadView();","if(!['discover','curated'].includes(state.view))setView('discover');else loadView();")
text=text.replace("${movie.year??'—'} <span>·</span>","${movie.year??'—'} ${movie.media_type==='series'?' · SERIES':''} <span>·</span>")
text=text.replace('<div class="detail-actions">','${externalRatings(movie)}<div class="detail-actions">',1)
text=text.replace(' Điểm sao từ dữ liệu MovieLens.</p>',' Điểm MovieLens là dữ liệu lịch sử; điểm nguồn bên ngoài hiển thị riêng ở trên.</p>')
text=text.replace('Phim trong dữ liệu chủ yếu được phát hành đến năm ${stats.year_max}.','Lịch sử đánh giá MovieLens chủ yếu thuộc các phim đến năm 2000; catalog bổ sung có phim đến ${stats.year_max}. Phim mới dùng tín hiệu thể loại khi chưa có lịch sử đánh giá.')
path.write_text(text,encoding='utf-8')
