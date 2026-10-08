/* Shared, dependency-free film helpers for the browser and Netlify. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.cineFilms = factory();
})(typeof window === 'undefined' ? globalThis : window, function () {
  const genreNames = {Action:'Hành động',Adventure:'Phiêu lưu',Animation:'Hoạt hình',"Children's":'Gia đình',Comedy:'Hài',Crime:'Tội phạm',Documentary:'Tài liệu',Drama:'Chính kịch',Fantasy:'Kỳ ảo','Film-Noir':'Film Noir',Horror:'Kinh dị',Musical:'Nhạc kịch',Mystery:'Bí ẩn',Romance:'Lãng mạn','Sci-Fi':'Khoa học viễn tưởng',Thriller:'Giật gân',War:'Chiến tranh',Western:'Cao bồi'};
  const searchKey = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[đĐ]/g,'d').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
  const displayTitle = title => String(title || '').normalize('NFC').replace(/^(.+),\s*(The|A|An|Le|La|Les|El|Il)(\s*\([^)]*\))?$/, '$2 $1$3');
  function audienceRating(movie) {
    if (Number.isFinite(movie.rating) && movie.rating > 0 && movie.rating <= 5)
      return {provider:'MovieLens',value:movie.rating,scale:5,normalized:movie.rating,count:movie.rating_count || 0};
    // Approval percentages and critic scores are not average audience stars.
    for (const provider of ['Letterboxd','IMDb','MUBI','Metacritic']) {
      const rating=(movie.external_ratings || []).find(r=>r.provider===provider && r.audience==='audience' && [5,10].includes(r.scale) && Number.isFinite(r.value) && r.value>0 && r.value<=r.scale);
      if (rating) return {...rating,normalized:rating.value*5/rating.scale};
    }
    return null;
  }
  function matchesQuery(movie, query) {
    const words=searchKey(query).split(/\s+/).filter(Boolean);
    const text=searchKey([displayTitle(movie.title),movie.full_title,movie.title_vi,...(movie.title_aliases || []),movie.year,movie.imdb_id,...(movie.directors || []),...(movie.genres || '').split('|').map(g=>genreNames[g] || g)].join(' '));
    return words.every(word=>text.includes(word));
  }
  function localDay() { return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()); }
  const regions={VN:'Việt Nam',US:'Mỹ',GB:'Anh',FR:'Pháp',JP:'Nhật Bản',KR:'Hàn Quốc'};
  function releaseEvents(movie, region='') {
    const unique=new Map();
    for(const event of [movie.release,...(movie.releases || [])])if(event?.date && (!region || event.region===region))unique.set(event.region+'|'+event.date,event);
    return [...unique.values()];
  }
  function releaseState(movie, day, region='') {
    const event=releaseEvents(movie,region)[0];
    if(!event)return '';
    day ||= localDay();
    const age=(Date.parse(day)-Date.parse(event.date))/86400000;
    return age<0?'upcoming':age<=30?'recent':'released';
  }
  function matchesRelease(movie, mode, day, region='') {
    if(mode==='vn-now'){mode='screening';region='VN';}
    if(mode==='vn-upcoming'){mode='upcoming';region='VN';}
    if(mode==='screening'){
      const age=(Date.parse(day || localDay())-Date.parse(movie.cinema_status?.checked_at))/86400000;
      return movie.cinema_status?.status==='now' && (!region || movie.cinema_status.region===region) && age>=0 && age<=7;
    }
    const events=releaseEvents(movie,region);
    if(mode==='released')return events.some(event=>Date.parse(event.date)<=Date.parse(day || localDay())) && !matchesRelease(movie,'screening',day,region);
    if(mode==='recent' || mode==='upcoming')return events.some(event=>releaseState({release:event},day)===mode);
    return (!mode || mode==='all') && (!region || events.length>0);
  }
  function unreleased(movie, day, region='') {
    const events=releaseEvents(movie,region);
    return events.length>0 && events.every(event=>releaseState({release:event},day)==='upcoming');
  }
  function releaseLabel(movie, region='', mode='all') {
    if((!region || region==='VN') && mode!=='released' && matchesRelease(movie,'screening'))return 'Đang chiếu · Việt Nam · Galaxy · '+movie.cinema_status.checked_at.split('-').reverse().join('/');
    const events=releaseEvents(movie,region);
    const event=(mode==='released'?events.find(r=>Date.parse(r.date)<=Date.parse(localDay())):['recent','upcoming'].includes(mode)?events.find(r=>releaseState({release:r})===mode):null) || events[0];
    if(!event)return '';
    const status=releaseState({release:event}),date=event.date.split('-').reverse().join('/');
    return `${status==='upcoming'?'Sắp chiếu · dự kiến':mode==='recent'?'Mới công chiếu · theo lịch':'Đã phát hành'} ${date} · ${regions[event.region] || event.region}`;
  }
  function searchSuggestions(movies, query) {
    const words=searchKey(query).split(' ').filter(Boolean);
    if(!words.length || words.some(w=>w.length<4) || words.join(' ').length>80)return [];
    const distance=(a,b)=>{
      if(Math.abs(a.length-b.length)>2)return 3;
      let previous=Array.from({length:b.length+1},(_,i)=>i);
      for(let i=1;i<=a.length;i++){
        const next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(next[j-1]+1,previous[j]+1,previous[j-1]+(a[i-1]!==b[j-1]));previous=next;
      }
      return previous[b.length];
    };
    return movies.map(m=>{
      const tokens=searchKey(displayTitle(m.title)).split(' ');
      const differences=words.map(w=>Math.min(...tokens.map(t=>distance(w,t))));
      return {movie:m,distance:differences.reduce((s,n)=>s+n,0),matches:differences.every(n=>n<=1)};
    }).filter(r=>r.matches && r.distance>0).sort((a,b)=>a.distance-b.distance||(b.movie.rating_count || 0)-(a.movie.rating_count || 0)).slice(0,5).map(r=>({movie_id:r.movie.movie_id,title:displayTitle(r.movie.title),year:r.movie.year}));
  }
  function collectionMovies(movies, options={}) {
    const filtered=movies.filter(m=>matchesQuery(m,options.q) && (!options.genre || m.genres.split('|').includes(options.genre)) && (options.yearMin==null || m.year>=options.yearMin && m.year<=options.yearMax) && (options.status!=='rated' || m.my_rating>0) && (options.status!=='unrated' || !m.my_rating));
    const title=(a,b)=>displayTitle(a.title).localeCompare(displayTitle(b.title),'vi',{numeric:true});
    const sort=options.sort || 'title';
    return filtered.sort((a,b)=>(sort==='personal'?(b.my_rating || 0)-(a.my_rating || 0):sort==='rating'?(audienceRating(b)?.normalized || 0)-(audienceRating(a)?.normalized || 0):sort==='year'?(b.year || 0)-(a.year || 0):sort==='popular'?(b.rating_count || 0)-(a.rating_count || 0):0) || title(a,b));
  }
  return {genreNames,searchKey,displayTitle,audienceRating,matchesQuery,collectionMovies,searchSuggestions,releaseState,matchesRelease,releaseLabel,localDay,regions,releaseEvents,unreleased};
});
