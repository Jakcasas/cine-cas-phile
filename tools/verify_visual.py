"""Smoke-test cropped known scene references, not general recognition accuracy."""
from io import BytesIO
import hashlib
import json
from src import settings
from src.api.vision import VisualSearch, decode_image
from src.recommenders.engine import fingerprint


def main():
    visual=VisualSearch(settings.ROOT/'artifacts/vision',fingerprint(settings.DATA_DIR))
    results=[]
    indices=[i for i,(mid,kind) in enumerate(zip(visual.movie_ids,visual.kinds)) if kind=='still']
    # Include a familiar film for the browser demonstration, then other real stills.
    indices.sort(key=lambda i:int(visual.movie_ids[i])!=2571)
    for i in indices[:5]:
        file=settings.ROOT/'runtime/reference-images'/(hashlib.sha256(str(visual.urls[i]).encode()).hexdigest()+'.img')
        original=decode_image(file.read_bytes());w,h=original.size
        cropped=original.crop((int(w*.05),int(h*.05),int(w*.95),int(h*.95))).resize((640,360))
        buffer=BytesIO();cropped.save(buffer,format='PNG');data=buffer.getvalue()
        matches=visual.search(data,5)
        expected=int(visual.movie_ids[i]);found=matches[0]['movie_id']
        results.append({'expected_movie_id':expected,'first_match_movie_id':found,'pass':found==expected,'score':matches[0]['visual_similarity']})
        if not (settings.ROOT/'runtime/scene-example.png').exists():(settings.ROOT/'runtime/scene-example.png').write_bytes(data)
    report={'checks':results,'note':'Cropped/resized known reference images only; this is a pipeline check, not unseen-scene identification accuracy.'}
    (settings.ROOT/'reports/visual_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
    assert all(row['pass'] for row in results)


if __name__=='__main__':main()
