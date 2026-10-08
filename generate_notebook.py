"""Create an unexecuted notebook with examples of the production engine."""
import json
from pathlib import Path


def markdown(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.splitlines(keepends=True)}


cells = [
    markdown("# Cine Cas Phile\n\nRun from the project root. Offline evaluation and the web API share one engine."),
    code("from src.cli import dataset, load_engine\nloader, movies, ratings = dataset()\nloader.get_stats()"),
    code("from src.data.splitter import TemporalSplitter\ntrain, validation, test, manifest = TemporalSplitter().split(ratings)\nmanifest"),
    code("engine = load_engine()\nengine.recommend(preferred_genres=['Sci-Fi'], k=5)"),
    code("engine.recommend(user_id=1, model='svd', k=5)"),
    code("import json\nfrom pathlib import Path\nimport pandas as pd\nreport = json.loads(Path('reports/benchmark.json').read_text())\npd.DataFrame(report['results'])"),
    markdown("## Limits\n\nPer-user time splitting is not a global chronological split. Full catalog metadata is assumed available. Content and hybrid scores are not calibrated ratings. Compare actual benchmark results instead of assuming an ensemble always wins."),
]

if __name__ == "__main__":
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}
    Path("Cine_Cas_Phile.ipynb").write_text(json.dumps(notebook, indent=2), encoding="utf-8")
