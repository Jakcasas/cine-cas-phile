"""Serving regressions: holdout exclusion, exact genres, persistence and fallback."""
import numpy as np
import pandas as pd
import pytest
from src.recommenders.engine import RecommendationEngine, MODELS
from src.api.profiles import ProfileStore
from src.data.loader import MovieLensLoader
from src.data.splitter import TemporalSplitter


@pytest.fixture
def fitted():
    genres = ["Action|Sci-Fi", "Action|Thriller", "Drama", "Comedy", "Sci-Fi", "Film-Noir|Crime", "Children's|Animation", "Drama|Romance"]
    movies = pd.DataFrame([{"movie_id":i+1,"title":f"Film {i+1} (1995)","title_clean":f"Film {i+1}","year":1995,"genres":g,"genres_list":g.split('|')} for i,g in enumerate(genres)])
    ratings = pd.DataFrame([{"user_id":u,"movie_id":mid,"rating":float((mid+u)%5+1),"timestamp":100+mid} for u in range(1,6) for mid in range(1,6)])
    return RecommendationEngine(movies).fit(ratings, factors=3, neighbors=3)


@pytest.mark.parametrize("model", MODELS)
def test_candidates_are_unseen_unique_and_finite(fitted, model):
    recs=fitted.recommend(user_id=1,model=model,k=5,exclude_ids=[6],diversity=.25)
    assert {row['movie_id'] for row in recs} == {7,8}
    assert all(np.isfinite(row['score']) and 0<=row['score']<=1 for row in recs)


def test_cold_start_preserves_atomic_genres(fitted):
    assert 'sci-fi' in fitted.genre_index and 'film-noir' in fitted.genre_index and "children's" in fitted.genre_index
    recs=fitted.recommend(preferred_genres=['Sci-Fi'],model='content',seed_ids=[1],diversity=0)
    assert recs[0]['movie_id']==5
    assert 1 not in {r['movie_id'] for r in recs}


def test_session_ratings_change_taste_and_exclude_watched(fitted):
    recs=fitted.recommend(ratings={3:5},model='content',diversity=0)
    assert recs[0]['movie_id']==8
    assert 3 not in {r['movie_id'] for r in recs}
    filtered=fitted.recommend(genre='Comedy',ratings={4:1})
    assert filtered==[]


def test_filters_and_validation(fitted):
    assert all('Drama' in r['genres'] for r in fitted.recommend(genre='Drama'))
    assert fitted.recommend(year_min=2000)==[]
    for kwargs in ({'genre':'Unknown'},{'model':'neural'},{'year_min':2000,'year_max':1990},{'seed_ids':[999]},{'diversity':2}):
        with pytest.raises(ValueError): fitted.recommend(**kwargs)


def test_similarity_never_returns_itself(fitted):
    assert 3 not in {r['movie_id'] for r in fitted.similar(3)}


def test_safe_artifact_round_trip_and_stale_rejection(fitted,tmp_path):
    path=tmp_path/'model.npz'
    fitted.save(path,'dataset-a',{'protocol':'test'})
    loaded=RecommendationEngine(fitted.movies).load(path,'dataset-a')
    assert fitted.recommend(user_id=1)==loaded.recommend(user_id=1)
    with pytest.raises(ValueError): RecommendationEngine(fitted.movies).load(path,'dataset-b')


def test_profiles_survive_reopening_and_are_isolated(tmp_path):
    store=ProfileStore(tmp_path/'profiles.sqlite3');store.initialize()
    first=store.create()['profile_id']; second=store.create()['profile_id']
    store.rate(first,1,5);store.rate(first,1,4);store.watchlist(first,2,True);store.watchlist(first,2,True);store.preferences(first,['Sci-Fi'])
    reopened=ProfileStore(store.path)
    profile=reopened.get(first)
    assert profile['ratings']=={1:4.0} and profile['watchlist']==[2] and profile['genres']==['Sci-Fi']
    assert reopened.get(second)['ratings']=={}
    reopened.unrate(first,1);reopened.watchlist(first,2,False)
    assert reopened.get(first)['ratings']=={} and reopened.get(first)['watchlist']==[]
    assert store.get("' OR 1=1 --") is None


@pytest.mark.parametrize('suffix,content',[('dat','1::First (1990)::Sci-Fi\n2::Second (1991)::Drama\n'),('csv','movieId,title,genres\n1,First (1990),Sci-Fi\n2,Second (1991),Drama\n')])
def test_loader_preserves_first_row(tmp_path,suffix,content):
    path=tmp_path/f'movies.{suffix}';path.write_text(content,encoding='latin-1')
    movies=MovieLensLoader(raw_movies_path=str(path)).load_movies()
    assert movies.movie_id.tolist()==[1,2]
    assert movies.iloc[0].title=='First (1990)'


def test_equal_timestamps_remain_atomic():
    ratings=pd.DataFrame([{'user_id':1,'movie_id':i,'rating':4.,'timestamp':i//4} for i in range(20)])
    train,val,test,manifest=TemporalSplitter().split(ratings)
    assert len(train)+len(val)+len(test)==len(ratings)
    time_sets=[set(frame.timestamp) for frame in (train,val,test)]
    assert not time_sets[0]&time_sets[1] and not time_sets[1]&time_sets[2] and not time_sets[0]&time_sets[2]
    assert not manifest['leakage_detected']


def test_split_rejects_duplicate_pairs():
    ratings=pd.DataFrame([{'user_id':1,'movie_id':1,'rating':4.,'timestamp':i} for i in range(6)])
    with pytest.raises(ValueError):TemporalSplitter().split(ratings)
