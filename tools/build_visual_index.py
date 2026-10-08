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
    enrichment=MovieEnrichment(settings.ROOT/'data'/'enrichment'/'movie_images.json')
    references=[]
    for mid,entry in enrichment.movies.items():
        for url in entry.get('still_urls',[]):references.append((mid,'still',[url]))
        priority={'Letterboxd':0,'MUBI':1,'PhimMoi':2,'FshareTV':3}
        sources=sorted(entry['poster_sources'],key=lambda s:priority[s['name']])
        urls=list(dict.fromkeys(url for source in sources for url in [source['image_url'],source['fallback_url']] if url))
        if urls:references.append((mid,'poster',urls))
    cache=settings.ROOT/'runtime'/'reference-images';cache.mkdir(parents=True,exist_ok=True)

    def reference(item):
        mid,kind,urls=item
        for url in urls:
            if not safe_url(url,IMAGE_HOSTS):continue
            file=cache/(hashlib.sha256(url.encode()).hexdigest()+'.img')
            try:
                if file.exists():data=file.read_bytes()
                else:
                    request=Request(url,headers={'User-Agent':'CineCasPhile/1.0'})
                    with urlopen(request,timeout=12) as response:
                        if not safe_url(response.geturl(),IMAGE_HOSTS):continue
                        data=response.read(8*1024*1024+1)
                    decode_image(data);file.write_bytes(data)
                return mid,kind,url,decode_image(data)
            except Exception:continue
        return None

    folder=settings.ROOT/'artifacts'/'vision'
    encoder=ClipEncoder(folder)
    ids=[];kinds=[];urls=[];vectors=[];batch=[];failed=0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for count,result in enumerate(pool.map(reference,references),1):
            if result:batch.append(result)
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
                        catalog_fingerprint=fingerprint(settings.DATA_DIR))
    report={'reference_images':len(ids),'movies':len(set(ids)),'stills':kinds.count('still'),
            'unavailable_images':failed,'method':'CLIP ViT-B/32 INT8, cosine similarity; not an identification probability'}
    (settings.ROOT/'reports'/'visual_index.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
