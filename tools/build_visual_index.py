"""Download reference images for CLIP indexing; never downloads film/video files."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from urllib.request import Request, urlopen
import numpy as np
from src import settings
from src.api.enrichment import MovieEnrichment, safe_url, IMAGE_HOSTS
from src.api.vision import ClipEncoder, decode_image
from src.recommenders.engine import fingerprint


def main():
    folder=settings.ROOT/'artifacts'/'vision'
    encoder_hash=hashlib.sha256()
    for file in [folder/'clip-vit-b32-int8.onnx',folder/'preprocessor_config.json',settings.ROOT/'src/api/vision.py']:
        encoder_hash.update(file.read_bytes())
    encoder_fingerprint=encoder_hash.hexdigest()
    cached_vectors={}
    index_file=folder/'image_index.npz'
    if index_file.exists():
        # This update keeps the same CLIP encoder and preprocessing. Reuse
        # vectors only for the same film ID, image kind and exact source URL.
        with np.load(index_file,allow_pickle=False) as old:
            if 'encoder_fingerprint' in old and str(old['encoder_fingerprint'])==encoder_fingerprint:
                cached_vectors={(int(mid),str(kind),str(url)):vector.copy() for mid,kind,url,vector in zip(old['movie_ids'],old['kinds'],old['urls'],old['embeddings'])}
    enrichment=MovieEnrichment(settings.ROOT/'data'/'enrichment'/'movie_images.json')
    references=[]
    for mid,entry in enrichment.movies.items():
        for url in entry.get('still_urls',[]):references.append((mid,'still',[url]))
        priority={'Letterboxd':0,'MUBI':1,'Galaxy Cinema':2,'IMDb':3,'PhimMoi':4,'FshareTV':5}
        sources=sorted(entry['poster_sources'],key=lambda s:priority.get(s['name'],3))
        urls=list(dict.fromkeys(url for source in sources for url in [source['image_url'],source['fallback_url']] if url))
        if urls:references.append((mid,'poster',urls))
    cache=settings.ROOT/'runtime'/'reference-images';cache.mkdir(parents=True,exist_ok=True)

    def reference(item):
        mid,kind,urls=item
        for url in urls:
            if not safe_url(url,IMAGE_HOSTS):continue
            if (mid,kind,url) in cached_vectors:return mid,kind,url,None,cached_vectors[(mid,kind,url)]
            file=cache/(hashlib.sha256(url.encode()).hexdigest()+'.img')
            try:
                if file.exists():data=file.read_bytes()
                else:
                    request=Request(url,headers={'User-Agent':'CineCasPhile/1.0'})
                    with urlopen(request,timeout=12) as response:
                        if not safe_url(response.geturl(),IMAGE_HOSTS):continue
                        data=response.read(8*1024*1024+1)
                    decode_image(data);file.write_bytes(data)
                return mid,kind,url,decode_image(data),None
            except Exception:continue
        return None

    encoder=ClipEncoder(folder)
    ids=[];kinds=[];urls=[];vectors=[];batch=[];failed=0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for count,result in enumerate(pool.map(reference,references),1):
            if result and result[4] is not None:
                ids.append(result[0]);kinds.append(result[1]);urls.append(result[2]);vectors.append(result[4])
            elif result:batch.append(result)
            else:failed+=1
            if len(batch)>=8 or (count==len(references) and batch):
                embeddings=encoder.encode([item[3] for item in batch])
                for item,vector in zip(batch,embeddings):
                    ids.append(item[0]);kinds.append(item[1]);urls.append(item[2]);vectors.append(vector)
                batch=[]
            if count%100==0:print(f'Images {count}/{len(references)}, indexed {len(ids)}, unavailable {failed}',flush=True)
    if not vectors:raise RuntimeError('No reference images could be indexed')
    np.savez_compressed(folder/'image_index.npz',embeddings=np.asarray(vectors,dtype=np.float32),
                        movie_ids=np.asarray(ids,dtype=np.int64),kinds=np.asarray(kinds),urls=np.asarray(urls),
                        catalog_fingerprint=fingerprint(settings.DATA_DIR),encoder_fingerprint=encoder_fingerprint)
    report={'reference_images':len(ids),'movies':len(set(ids)),'stills':kinds.count('still'),
            'unavailable_images':failed,'method':'CLIP ViT-B/32 INT8, cosine similarity; not an identification probability'}
    (settings.ROOT/'reports'/'visual_index.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
