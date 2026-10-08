from pathlib import Path
import re
path=Path(__file__).resolve().parents[1]/'web/index.html'
text=path.read_text(encoding='utf-8')
text=text.replace('Cine Cas Phile — Một bộ phim hay. Một thế giới khác.','Cine Cas Phile — One film, one fish fillet.')
text=re.sub(r'<h1>.*?</h1>','<h1>One film, one fish fillet.</h1><div class="hero-slogan-fr" lang="fr">(Un film, un filet de poisson.)</div>',text,count=1,flags=re.S)
text=text.replace('For the love of cinema.','One film, one fish fillet. (Un film, un filet de poisson.)')
text=text.replace('<br>',' ')
path.write_text(text,encoding='utf-8')
path=path.parent/'app.js';text=path.read_text(encoding='utf-8');text=text.replace('<br>',' ')
path.write_text(text,encoding='utf-8')
