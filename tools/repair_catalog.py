"""One-time consolidation of verified duplicate editorial title/year pairs."""
import csv
import json
from src import settings
from src.data.catalog import load_catalog
from tools.sync_movie_images import aliases


def main():
    movies=load_catalog(settings.DATA_DIR)
    index={};remap={}
    for row in movies.itertuples():
        keys=[(key,int(row.year)) for key in aliases(row.title)]
        candidates={index[key] for key in keys if key in index}
        if row.movie_id>=1_000_000 and len(candidates)==1:
            remap[row.movie_id]=candidates.pop()
        for key in keys:index.setdefault(key,remap.get(row.movie_id,row.movie_id))
    path=settings.DATA_DIR/'catalog_extra.csv'
    with path.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['movie_id','title','genres']);writer.writeheader()
        writer.writerows(row for row in rows if int(row['movie_id']) not in remap)
    path=settings.ROOT/'data/enrichment/editorial.json'
    data=json.loads(path.read_text(encoding='utf-8'));entries=data['movies']
    for old,new in remap.items():
        entry=entries.pop(str(old),{})
        target=entries.setdefault(str(new),{})
        for key,value in entry.items():
            if isinstance(value,list):
                target[key]=target.get(key,[])+[v for v in value if v not in target.get(key,[])]
            elif value is not None:target[key]=value
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(remap)


if __name__=='__main__':main()
