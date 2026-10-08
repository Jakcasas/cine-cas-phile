from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
app = ROOT / 'web/app.js'
text = app.read_text(encoding='utf-8')
text = text.replace('<p>Đo trên ${format(report.rating_pairs)}', '<p>${report.runtime_note?escapeHtml(report.runtime_note):""}</p><p>Đo trên ${format(report.rating_pairs)}')
app.write_text(text, encoding='utf-8')
