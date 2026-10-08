"use strict";
window.cineClub = (() => {
  let config={online:false,providers:{}},user=null,accountTab='guest',communityTab='chat',surveySeed=null,seedTimer;
  async function cloud(path, method='GET', body) {
    const response=await fetch('/club'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
    let data;try{data=await response.json();}catch{throw new Error('Cộng đồng chưa sẵn sàng. Bạn vẫn có thể lưu phim ở chế độ khách.');}
    if(!response.ok)throw new Error(data.detail || 'Không thể hoàn tất thao tác.');
    return data;
  }
  const profilePayload=p=>({ratings:p.ratings || {},watchlist:p.watchlist || [],seen:p.seen || [],genres:p.genres || [],survey:p.survey || {}});
  async function sync(p){if(user)await cloud('/profile','PUT',profilePayload(p));}
  function identity(){
    let nickname='Khách';try{nickname=localStorage.getItem('cine-guest-name') || 'Khách';}catch{}
    $('#identity-label').textContent=user?`${user.name} · ${user.guest?'Khách online':'Đã đồng bộ online'}`:`${nickname} · lưu trên thiết bị`;
    $('#account-open').textContent=user?user.name:nickname==='Khách'?'Đăng nhập / Khách':nickname;
    $('#logout').hidden=!user;
    $('#delete-account').hidden=!user;
  }
  function tabs(tab){
    accountTab=tab;
    $('#name-field').hidden=tab==='login';$('#email-fields').hidden=tab==='guest';$('#anonymous-field').hidden=tab!=='guest';
    $('#account-submit').textContent={guest:'Tiếp tục với tư cách khách',login:'Đăng nhập',register:'Tạo tài khoản'}[tab];
    $('#account-form [name=email]').required=tab!=='guest';$('#account-form [name=password]').required=tab!=='guest';
    $('#account-form [name=password]').autocomplete=tab==='register'?'new-password':'current-password';
    $('#account-submit').disabled=tab!=='guest'&&!config.online;
    document.querySelectorAll('[data-account-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.accountTab===tab)));
  }
  function account(){
    tabs('guest');
    $('#account-notice').textContent=config.online?'Tài khoản đồng bộ bộ sưu tập online. Khách có thể dùng biệt danh hoặc Ẩn danh.':'Khách vẫn dùng đầy đủ khảo sát, lưu phim và chấm sao. Đăng ký online sẽ mở khi dịch vụ tài khoản sẵn sàng.';
    for(const provider of ['google','facebook']){const a=$('#'+provider+'-login');a.hidden=!config.providers[provider];}
    $('#account-status').textContent='';$('#account-dialog').showModal();
  }
  async function activate(data, merge=false){
    const guest=profilePayload(state.profile);
    user=data.user;
    const p=data.profile || {};
    const next=merge?{...p,watchlist:[...new Set([...(p.watchlist || []),...guest.watchlist])],seen:[...new Set([...(p.seen || []),...guest.seen])],ratings:{...guest.ratings,...p.ratings},genres:p.genres?.length?p.genres:guest.genres,survey:Object.keys(p.survey || {}).length?p.survey:guest.survey}:p;
    window.cineCloudProfile={...next,profile_id:state.profile.profile_id || crypto.randomUUID()};
    if(merge)await sync(next);
    state.profile=await api('/profiles/'+window.cineCloudProfile.profile_id);renderProfile();identity();renderTaste();
  }
  async function init(){
    const auth=new URLSearchParams(location.search).get('auth');
    try{config=await cloud('/config');if(config.online){const data=await cloud('/auth/me');if(data.user)await activate(data,auth==='success');}}catch{}
    state.profile.seen ??= [];state.profile.survey ??= {};identity();renderTaste();
    if(auth){history.replaceState({},'',location.pathname);if(auth==='success'&&user)toast('Đã đăng nhập. Bộ sưu tập online đã sẵn sàng.');else if(auth==='cancelled')toast('Bạn đã hủy đăng nhập. Bộ sưu tập trên thiết bị vẫn được giữ.');}
  }
  function prepareSurvey(){
    const survey=state.profile.survey || {};
    $('#taste-form [name=era]').value=survey.era || '';$('#taste-form [name=mood]').value=survey.mood || '';
    $('#avoid-options').innerHTML=state.stats.genres.map(g=>`<label class="taste-option"><input type="checkbox" name="avoid" value="${escapeHtml(g)}" ${(survey.avoid || []).includes(g)?'checked':''}><span>${escapeHtml(genreLabel(g))}</span></label>`).join('');
    surveySeed=survey.seed_ids?.[0] || null;$('#survey-seed-chosen').dataset.title=survey.seed_title || '';$('#survey-seed-chosen').textContent=survey.seed_title?'Phim bạn thích: '+displayTitle(survey.seed_title):'Chưa chọn phim · không bắt buộc';
    $('#survey-seed-clear').hidden=!surveySeed;
    $('#survey-seed-results').innerHTML='';$('#survey-seed-search').value='';
  }
  function survey(form){const d=new FormData(form);return {era:d.get('era'),mood:d.get('mood'),avoid:d.getAll('avoid'),seed_ids:surveySeed?[surveySeed]:[],seed_title:surveySeed?$('#survey-seed-chosen').dataset.title || '':''};}
  function renderTaste(){
    const p=state.profile,s=p.survey || {},parts=[];
    const moods={gentle:'Nhẹ nhàng, ấm áp',intense:'Hồi hộp, bí ẩn',wonder:'Kỳ thú, khác lạ',thoughtful:'Suy ngẫm, sâu lắng'};
    if(p.genres?.length)parts.push('Bạn thích '+p.genres.map(genreLabel).join(', '));
    if(s.era)parts.push('Thời kỳ '+s.era.replace(':','–'));
    if(moods[s.mood])parts.push(moods[s.mood]);
    if(s.seed_title)parts.push('Lấy cảm hứng từ '+displayTitle(s.seed_title));
    if(s.avoid?.length)parts.push('Muốn tránh '+s.avoid.map(genreLabel).join(', '));
    $('#taste-summary').textContent=parts.length?parts.join(' · '):'Chọn thể loại hoặc làm khảo sát để tìm phim phù hợp.';
  }
  function renderPosts(posts){return posts.length?posts.map(p=>`<article class="community-post"><div class="post-author"><span class="avatar">${escapeHtml(p.author.slice(0,1))}</span><strong>${escapeHtml(p.author)}</strong><time>${escapeHtml(new Date(p.createdAt).toLocaleDateString('vi-VN'))}</time></div>${p.movieTitle?`<h3><button class="text-button" data-movie="${p.movieId}">${escapeHtml(displayTitle(p.movieTitle))}</button> <span class="review-stars">${'★'.repeat(Math.floor(p.rating || 0))}${p.rating%1?'½':''}</span></h3>`:''}${p.title?`<h3>${escapeHtml(p.title)}</h3>`:''}${p.spoiler?`<details><summary>Có tiết lộ tình tiết · nhấn để đọc</summary><p class="post-content">${escapeHtml(p.content)}</p></details>`:`<p class="post-content">${escapeHtml(p.content)}</p>`}<div class="post-actions"><button type="button" data-like="${p.id}" aria-pressed="${!!p.liked}" ${p.liked?'disabled':''}>♡ ${p.likes || 0}</button><button type="button" data-report="${p.id}">Báo cáo</button>${p.canRemove?`<button type="button" data-remove-post="${p.id}">Gỡ bài của tôi</button>`:''}</div></article>`).join(''):'<div class="community-empty"><h3>Cuộc trò chuyện bắt đầu từ bạn.</h3><p>Chưa có bài viết ở đây. Chia sẻ bộ phim hoặc góc nhìn đầu tiên của bạn.</p></div>';}
  async function feed(){
    $('#chat-form').hidden=communityTab!=='chat';$('#community-status').textContent='Đang tải…';
    const tab=communityTab;
    try{const d=await cloud('/posts?kind='+tab);if(tab!==communityTab)return;$('#community-feed').innerHTML=renderPosts(d.posts);$('#community-status').textContent='';}
    catch(error){$('#community-feed').innerHTML='';$('#community-status').textContent=error.message;}
  }
  function community(tab='chat'){communityTab=tab;$('#community-dialog').showModal();feed();}
  async function decorateDetail(movie){
    const seen=(state.profile.seen || []).includes(movie.movie_id)||Boolean(state.profile.ratings[movie.movie_id]);
    $('#movie-detail').insertAdjacentHTML('beforeend',`<section class="diary-panel"><h3>Nhật ký của bạn</h3><button type="button" class="secondary" data-seen="${movie.movie_id}" aria-pressed="${seen}">${seen?'✓ Đã xem':'Đánh dấu đã xem'}</button><p>Lưu phim đã xem vào bộ sưu tập. Chấm sao hoặc viết một góc nhìn riêng.</p><form id="review-form" data-film="${movie.movie_id}"><label>Bài đánh giá<textarea name="content" rows="4" required maxlength="2000" placeholder="Bạn nghĩ gì về bộ phim này?"></textarea></label><div class="form-row"><label>Điểm của bạn<select name="rating">${[.5,1,1.5,2,2.5,3,3.5,4,4.5,5].map(r=>`<option value="${r}" ${Number(state.profile.ratings[movie.movie_id] || 4)===r?'selected':''}>${r} / 5 ★</option>`).join('')}</select></label><label><input name="spoiler" type="checkbox"> Có tiết lộ tình tiết</label><label><input name="anonymous" type="checkbox"> Đăng ẩn danh</label></div><button class="primary" type="submit">Chia sẻ đánh giá ↗</button><p class="review-status" role="status"></p></form></section>`);
  }
  for(const id of ['#survey-open','#survey-edit'])$(id).addEventListener('click',openTaste);
  $('#account-open').addEventListener('click',account);
  $('#community-open').addEventListener('click',()=>community());
  $('#community-reload').addEventListener('click',feed);
  $('#blog-open').addEventListener('click',()=>{$('#blog-dialog').showModal();});
  $('#feedback-open').addEventListener('click',()=>$('#feedback-dialog').showModal());
  $('#account-form').addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;$('#account-status').textContent='';
    try{
      const d=Object.fromEntries(new FormData(event.currentTarget));d.anonymous=Boolean(d.anonymous);
      if(accountTab==='guest'&&!config.online){const name=d.anonymous?'Ẩn danh':(d.name || 'Khách').normalize('NFC').trim().slice(0,40);try{localStorage.setItem('cine-guest-name',name);}catch{}identity();}
      else await activate(await cloud('/auth/'+accountTab,'POST',d),true);
      $('#account-dialog').close();toast('Chào mừng bạn đến với Cine.');loadView();
    }catch(error){$('#account-status').textContent=error.message;}finally{button.disabled=false;}
  });
  $('#logout').addEventListener('click',async()=>{try{await cloud('/auth/logout','POST',{});user=null;window.cineCloudProfile=null;state.profile=await api('/profiles/'+state.profile.profile_id);identity();renderProfile();renderTaste();$('#account-dialog').close();loadView();toast('Đã đăng xuất. Bạn đang dùng hồ sơ khách trên thiết bị.');}catch(error){$('#account-status').textContent=error.message;}});
  $('#delete-account').addEventListener('click',async()=>{
    if(!confirm('Xóa vĩnh viễn tài khoản, bộ sưu tập online và các bài viết của bạn? Thao tác này không thể hoàn tác.'))return;
    try{await cloud('/auth/delete','POST',{password:$('#account-form [name=password]').value});user=null;window.cineCloudProfile=null;state.profile=await api('/profiles/'+state.profile.profile_id);identity();renderProfile();$('#account-dialog').close();loadView();toast('Đã xóa tài khoản online.');}catch(error){$('#account-status').textContent=error.message;}
  });
  $('#survey-seed-search').addEventListener('input',()=>{clearTimeout(seedTimer);seedTimer=setTimeout(async()=>{const q=$('#survey-seed-search').value.trim();if(q.length<2){$('#survey-seed-results').innerHTML='';return;}try{const d=await api('/movies?q='+encodeURIComponent(q)+'&page_size=6');if(q!==$('#survey-seed-search').value.trim())return;$('#survey-seed-results').innerHTML=d.movies.map(m=>`<button type="button" class="secondary" data-survey-seed="${m.movie_id}" data-title="${escapeHtml(m.title)}">${escapeHtml(displayTitle(m.title))} · ${m.year}</button>`).join('')||'<p>Chưa tìm thấy. Thử tên gốc của phim.</p>';}catch(error){$('#survey-seed-results').textContent=error.message;}},250);});
  $('#survey-seed-clear').addEventListener('click',()=>{surveySeed=null;$('#survey-seed-chosen').dataset.title='';$('#survey-seed-chosen').textContent='Chưa chọn phim · không bắt buộc';$('#survey-seed-clear').hidden=true;});
  async function submit(form,path,statusId,extra={}){
    const b=form.querySelector('button[type=submit]');b.disabled=true;
    try{if(!user){account();throw new Error('Chọn tài khoản hoặc khách online để chia sẻ với cộng đồng.');}const d=Object.fromEntries(new FormData(form));d.anonymous=Boolean(d.anonymous);d.spoiler=Boolean(d.spoiler);if(d.rating)d.rating=Number(d.rating);await cloud(path,'POST',{...d,...extra});$(statusId).textContent='Đã gửi. Cảm ơn bạn đã chia sẻ!';form.reset();if(path==='/posts')feed();return true;}catch(error){$(statusId).textContent=error.message;return false;}finally{b.disabled=false;}
  }
  $('#chat-form').addEventListener('submit',event=>{event.preventDefault();submit(event.currentTarget,'/posts','#community-status',{kind:'chat'});});
  $('#blog-form').addEventListener('submit',async event=>{event.preventDefault();if(await submit(event.currentTarget,'/posts','#blog-status',{kind:'blog'})){try{localStorage.removeItem('cine-blog-draft');}catch{}}});
  $('#feedback-form').addEventListener('submit',event=>{event.preventDefault();submit(event.currentTarget,'/feedback','#feedback-status');});
  $('#blog-form').addEventListener('input',()=>{try{localStorage.setItem('cine-blog-draft',JSON.stringify(Object.fromEntries(new FormData($('#blog-form')))));}catch{}});
  try{const draft=JSON.parse(localStorage.getItem('cine-blog-draft') || 'null');if(draft)for(const key of ['title','content'])$('#blog-form [name='+key+']').value=draft[key] || '';}catch{}
  $('#collection-export').addEventListener('click',()=>{const blob=new Blob([JSON.stringify({version:'1.0',...profilePayload(state.profile)},null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='cine-cas-phile-collection.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);});
  document.addEventListener('submit',async event=>{if(event.target.id!=='review-form')return;event.preventDefault();const form=event.target,id=Number(form.dataset.film),rating=Number(new FormData(form).get('rating'));if(await submit(form,'/posts','#review-form .review-status',{kind:'review',movieId:id})){try{await send('/profiles/'+state.profile.profile_id+'/ratings/'+id,'PUT',{rating});state.profile.ratings[id]=rating;renderProfile();toast('Đã chia sẻ đánh giá và lưu điểm vào bộ sưu tập.');}catch(error){toast('Bài đã đăng; chưa đồng bộ điểm: '+error.message);}}});
  document.addEventListener('click',async event=>{
    const b=event.target.closest('button');if(!b)return;
    try{
      if(b.dataset.accountTab){tabs(b.dataset.accountTab);return;}
      if(b.dataset.communityTab){communityTab=b.dataset.communityTab;feed();return;}
      if(b.dataset.surveySeed){surveySeed=Number(b.dataset.surveySeed);$('#survey-seed-chosen').textContent='Phim bạn thích: '+displayTitle(b.dataset.title);$('#survey-seed-chosen').dataset.title=b.dataset.title;$('#survey-seed-results').innerHTML='';$('#survey-seed-clear').hidden=false;return;}
      if(b.dataset.seen){const id=Number(b.dataset.seen),seen=(state.profile.seen || []).includes(id);await send('/profiles/'+state.profile.profile_id+'/seen/'+id,seen?'DELETE':'PUT');state.profile.seen=seen?state.profile.seen.filter(mid=>mid!==id):[...new Set([...(state.profile.seen || []),id])];await showDetail(id);if(state.view==='ratings')loadView();toast(seen?'Đã bỏ dấu đã xem':'Đã thêm vào bộ sưu tập đã xem');return;}
      const id=b.dataset.like || b.dataset.report || b.dataset.removePost;if(!id)return;
      if(!user){account();return;}
      b.disabled=true;
      if(b.dataset.like)await cloud('/posts/'+id+'/like','POST',{});
      if(b.dataset.report){const reason=prompt('Lý do báo cáo nội dung (ít nhất 3 ký tự):');if(!reason){b.disabled=false;return;}await cloud('/posts/'+id+'/report','POST',{reason});toast('Đã ghi nhận báo cáo.');}
      if(b.dataset.removePost)await cloud('/posts/'+id+'/delete','POST',{});
      await feed();
    }catch(error){b.disabled=false;toast(error.message);}
  });
  setInterval(()=>{if($('#community-dialog').open && !document.hidden)feed();},30000);
  return {init,sync,prepareSurvey,survey,renderTaste,decorateDetail};
})();
