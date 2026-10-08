"""Update displayed brand text while preserving filenames, URLs and upstream originals."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
files = [ROOT/'README.md',ROOT/'src/api/main.py']
files += list((ROOT/'docs').glob('*.md'))
files += [ROOT/'web'/name for name in ['index.html','app.js','hosted-docs.html','assets/brand-preview.html']]
for path in files:
    text=path.read_text(encoding='utf-8')
    text=text.replace('Cine Cas Phile','Cine (cas) phile.').replace('CINE CAS PHILE','Cine (cas) phile.')
    text=text.replace('THE Cine (cas) phile. COLLECTION','Cine (cas) phile. / COLLECTION')
    path.write_text(text,encoding='utf-8')
