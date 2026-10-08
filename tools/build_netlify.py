"""Export the fitted engine for Node functions and a self-contained Netlify UI."""
from pathlib import Path
import gzip
import json
import shutil
import numpy as np
from src import settings
from src.api.service import RecommendationService

ROOT=settings.ROOT


def main():
    service=RecommendationService();service.initialize();engine=service.engine
    model={'movies':[service.enrich(engine.movie(int(mid))) for mid in engine.movie_ids],
           'genres':engine.genres,'global_mean':engine.global_mean,'features':engine.features.tolist(),
           'manifest':engine.manifest}
    for key in ['movie_ids','user_ids','user_means','profiles','counts','means','popularity','user_bias','item_bias','user_factors','item_factors']:
        model[key]=getattr(engine,key).tolist()
    for prefix in ['history','similarities']:
        matrix=getattr(engine,prefix)
        for key in ['data','indices','indptr']:model[prefix+'_'+key]=getattr(matrix,key).tolist()
    model['poster_movies']=sum(bool(e['poster_sources']) for e in service.enrichment.movies.values())
    destination=ROOT/'netlify/functions/data';destination.mkdir(parents=True,exist_ok=True)
    with gzip.open(destination/'model.json.gz','wt',encoding='utf-8') as f:json.dump(model,f,separators=(',',':'),allow_nan=False)
    benchmark=ROOT/'reports/benchmark.json';shutil.copyfile(benchmark,destination/'benchmark.json')
    output=ROOT/'dist/netlify';output.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'web',output/'static',dirs_exist_ok=True)
    html=(ROOT/'web/index.html').read_text(encoding='utf-8')
    html=html.replace('<script src="/static/app.js"','<script src="/static/hosted-adapter.js"></script><script src="/static/app.js"')
    html=html.replace('Hồ sơ được lưu trên máy.','Hồ sơ được lưu trong trình duyệt.')
    (output/'index.html').write_text(html,encoding='utf-8')
    ort=ROOT/'runtime/browser-onnx/node_modules/onnxruntime-web/dist'
    if not ort.exists():raise RuntimeError('Install onnxruntime-web under runtime/browser-onnx first')
    target=output/'static/ort';target.mkdir(parents=True,exist_ok=True)
    for name in ['ort.wasm.min.js','ort-wasm-simd-threaded.mjs','ort-wasm-simd-threaded.wasm']:
        shutil.copyfile(ort/name,target/name)
    license_path=ort.parent/'LICENSE'
    if license_path.exists():shutil.copyfile(license_path,target/'LICENSE.txt')
    model_dir=output/'static/vision';model_dir.mkdir(parents=True,exist_ok=True)
    data=(ROOT/'artifacts/vision/clip-vit-b32-int8.onnx').read_bytes();parts=[]
    for i,start in enumerate(range(0,len(data),8*1024*1024)):
        name=f'clip-{i:02}.bin';(model_dir/name).write_bytes(data[start:start+8*1024*1024]);parts.append(name)
    with np.load(ROOT/'artifacts/vision/image_index.npz',allow_pickle=False) as index:
        refs={'movie_ids':index['movie_ids'].tolist(),'urls':index['urls'].tolist(),'kinds':index['kinds'].tolist(),
              'model_parts':parts,'model_bytes':len(data),'dim':512,'stills':int((index['kinds']=='still').sum())}
        np.asarray(index['embeddings'],dtype='<f4').tofile(model_dir/'embeddings.bin')
    (model_dir/'references.json').write_text(json.dumps(refs,separators=(',',':')),encoding='utf-8')
    (ROOT/'artifacts/vision/web-references.json').write_text(json.dumps(refs,separators=(',',':')),encoding='utf-8')
    shutil.copyfile(model_dir/'embeddings.bin',ROOT/'artifacts/vision/web-embeddings.bin')
    shutil.copyfile(ROOT/'docs/CLIP_LICENSE.txt',model_dir/'LICENSE.txt')
    (output/'_redirects').write_text('/api/* /.netlify/functions/api/:splat 200\n/docs / 302\n',encoding='utf-8')
    print(f'Netlify build: {len(model["movies"])} films, {len(refs["movie_ids"])} image references, private model {(destination/"model.json.gz").stat().st_size:,} bytes')


if __name__=='__main__':main()
