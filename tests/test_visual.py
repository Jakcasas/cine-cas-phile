from io import BytesIO
import json
import numpy as np
from PIL import Image
import pytest
from src.api.vision import decode_image, VisualSearch
from src.api.enrichment import MovieEnrichment
from src.data.catalog import load_catalog


def png(size=(120,80)):
    f=BytesIO();Image.new('RGB',size,'red').save(f,format='PNG');return f.getvalue()


@pytest.mark.parametrize('data',[b'not an image',b'',b'x'*(8*1024*1024+1),png((8,8))],ids=['invalid','empty','oversize','tiny'])
def test_reject_invalid_uploads(data):
    with pytest.raises(ValueError):decode_image(data)


def test_valid_image_and_missing_or_stale_index(tmp_path):
    assert decode_image(png()).size==(120,80)
    search=VisualSearch(tmp_path,'new');assert not search.ready
    with pytest.raises(RuntimeError):search.search(png())
    np.savez(tmp_path/'image_index.npz',catalog_fingerprint='old')
    assert not VisualSearch(tmp_path,'new').ready


def test_retrieval_deduplicates_movie_with_multiple_references(tmp_path):
    np.savez(tmp_path/'image_index.npz',catalog_fingerprint='same',
             embeddings=np.array([[1,0],[.99,.01],[0,1]],dtype=np.float32),
             movie_ids=[4,4,9],kinds=['still','poster','still'],urls=['a','b','c'])
    search=VisualSearch(tmp_path,'same')
    class Encoder:
        def encode(self,images):return np.array([[1,0]],dtype=np.float32)
    search.encoder=Encoder()
    matches=search.search(png(),12)
    assert [m['movie_id'] for m in matches]==[4,9]
    assert matches[0]['matched_image_kind']=='still'


def test_external_scales_and_invalid_ratings_are_not_fabricated(tmp_path):
    path=tmp_path/'movie_images.json'
    entries=[{'provider':'Metacritic','audience':'critics','value':73,'scale':100,
              'url':'https://www.metacritic.com/movie/the-matrix/'},
             {'provider':'Letterboxd','audience':'audience','value':float('nan'),'scale':5,
              'url':'https://letterboxd.com/film/the-matrix/'},
             {'provider':'IMDb','audience':'audience','value':11,'scale':10,
              'url':'https://www.imdb.com/title/tt0133093/'}]
    path.write_text(json.dumps({'movies':{'2571':{'external_ratings':entries}}}))
    entry=MovieEnrichment(path).enrich({'movie_id':2571})
    assert len(entry['external_ratings'])==1
    assert entry['external_ratings'][0]['value']==73
    assert entry['poster_urls']==[]


def test_utf8_editorial_catalog_and_reserved_ids(tmp_path):
    (tmp_path/'movies.csv').write_text('movie_id,title,genres\n1,Toy Story (1995),Animation\n')
    extra=tmp_path/'catalog_extra.csv'
    extra.write_text('movie_id,title,genres\n1000000,La Mesías (2023),Thriller\n',encoding='utf-8')
    movies=load_catalog(tmp_path)
    assert movies.iloc[1].title=='La Mesías (2023)'
    extra.write_text('movie_id,title,genres\n2,Extra (2020),Drama\n')
    with pytest.raises(ValueError):load_catalog(tmp_path)
