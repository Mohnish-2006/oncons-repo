// shared.js - nav, auth helpers, API client
const API = window.ONCONS_API || (
  ['localhost','127.0.0.1',''].includes(location.hostname)
    ? 'http://localhost:8000/api'
    : '/api'
);

function tokenGet(){return localStorage.getItem('oncons_token')}
function refreshGet(){return localStorage.getItem('oncons_refresh_token')}
function tokenSet(t,refreshToken){
  localStorage.setItem('oncons_token',t);
  if(refreshToken) localStorage.setItem('oncons_refresh_token',refreshToken);
}
function tokenClear(){localStorage.removeItem('oncons_token');localStorage.removeItem('oncons_refresh_token');localStorage.removeItem('oncons_user')}
function userGet(){try{return JSON.parse(localStorage.getItem('oncons_user'))}catch{return null}}
function userSet(u){localStorage.setItem('oncons_user',JSON.stringify(u))}
function escapeHtml(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function showToast(message,type='ok'){
  let box=document.getElementById('toastRoot');
  if(!box){box=document.createElement('div');box.id='toastRoot';document.body.appendChild(box)}
  const item=document.createElement('div');
  item.className='toast show '+(type==='error'?'toast-error':'toast-ok');
  item.textContent=message;
  box.appendChild(item);
  setTimeout(()=>{item.classList.remove('show');setTimeout(()=>item.remove(),350)},3200);
}
function apiErrorMessage(data, fallback='Request failed'){
  const detail=data && (data.detail || data.message || data.error);
  if(Array.isArray(detail)){
    return detail.map(item=>{
      if(typeof item==='string') return item;
      const loc=Array.isArray(item.loc)?item.loc.filter(x=>x!=='body').join('.'):'';
      return (loc?loc+': ':'')+(item.msg || item.message || JSON.stringify(item));
    }).join(' ');
  }
  if(detail && typeof detail==='object') return detail.msg || detail.message || JSON.stringify(detail);
  if(typeof detail==='string') return detail;
  return fallback;
}
function skeletonRows(count=3){
  return Array.from({length:count},()=>'<div class="skeleton-line"></div>').join('');
}
function applyTheme(){
  const saved=localStorage.getItem('oncons_theme')||'light';
  document.documentElement.dataset.theme=saved;
}
function toggleTheme(){
  const next=(document.documentElement.dataset.theme||'light')==='dark'?'light':'dark';
  localStorage.setItem('oncons_theme',next);
  applyTheme();
}
applyTheme();

function paymentQrHtml(r){
  const qr=r.qr_url||'/assets/img/payment-qr.jpeg';
  return `${qr?`<img class="qr" src="${qr}" alt="Payment QR">`:''}
    <p>${r.upi_id?'UPI ID: '+r.upi_id:'UPI payment details are not configured.'}</p>
    ${r.upi_url?`<a class="btn btn-primary" href="${r.upi_url}">Open UPI app</a>`:''}`;
}

function loadScript(src){
  return new Promise((resolve,reject)=>{
    const existing=document.querySelector(`script[src="${src}"]`);
    if(existing){resolve();return}
    const script=document.createElement('script');
    script.src=src;
    script.onload=resolve;
    script.onerror=()=>reject(new Error('Could not load payment checkout. Check your internet connection.'));
    document.head.appendChild(script);
  });
}

async function startRazorpayPayment(r, statusBox, onPaid){
  if(!r || r.provider!=='razorpay') return false;
  if(!r.key || !r.order_id) throw new Error('Razorpay checkout is not configured correctly.');
  await loadScript('https://checkout.razorpay.com/v1/checkout.js');
  statusBox.innerHTML='<div class="payment-wait"><div class="mini-spinner"></div><strong>Opening secure Razorpay checkout...</strong></div>';
  return new Promise((resolve,reject)=>{
    const options={
      key:r.key,
      amount:Math.round(Number(r.amount||0)*100),
      currency:r.currency || 'INR',
      name:r.name || 'OnCons',
      description:r.description || 'OnCons payment',
      order_id:r.order_id,
      prefill:r.user || {},
      theme:{color:'#0d6e74'},
      handler:async function(response){
        try{
          statusBox.innerHTML='<div class="payment-wait"><div class="mini-spinner"></div><strong>Verifying payment with backend...</strong></div>';
          await api('/payments/razorpay/verify',{method:'POST',body:JSON.stringify({...response,payment_id:r.payment_id})});
          statusBox.innerHTML='<div class="alert alert-ok">Payment verified. Unlocking now...</div>';
          setTimeout(onPaid,700);
          resolve(true);
        }catch(err){reject(err)}
      },
      modal:{ondismiss:()=>{statusBox.innerHTML='<div class="alert alert-error">Payment was cancelled before completion.</div>';resolve(false)}}
    };
    const checkout=new Razorpay(options);
    checkout.on('payment.failed', response=>{
      const detail=response && response.error ? (response.error.description || response.error.reason) : 'Payment failed';
      statusBox.innerHTML='<div class="alert alert-error">'+escapeHtml(detail)+'</div>';
      reject(new Error(detail));
    });
    checkout.open();
  });
}

async function waitForPayment(paymentId, box, onPaid){
  let tries=0;
  const draw=(text)=>{box.insertAdjacentHTML?box.innerHTML=text:box.textContent=text};
  const tick=async()=>{
    tries+=1;
    const s=await api('/payments/'+paymentId+'/status');
    if(s.status==='paid'){
      draw('<div class="alert alert-ok">Payment verified automatically. Unlocking now...</div>');
      setTimeout(onPaid,700);
      return;
    }
    draw(`<div class="payment-wait"><div class="mini-spinner"></div><strong>Waiting for automatic payment verification...</strong><p>Do not close this page. Access unlocks only after verification is complete.</p></div>`);
    setTimeout(tick,2000);
  };
  tick().catch(err=>draw('<div class="alert alert-error">'+err.message+'</div>'));
}

async function refreshAccessToken(){
  const refreshToken=refreshGet();
  if(!refreshToken) return false;
  const res=await fetch(API+'/auth/refresh',{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:refreshToken})});
  const data=await res.json().catch(()=>({}));
  if(!res.ok){tokenClear();return false}
  tokenSet(data.access_token,data.refresh_token);
  if(data.user) userSet(data.user);
  return true;
}

async function api(path,opts={},retry=true){
  const h={'Content-Type':'application/json',...(opts.headers||{})};
  const tok=tokenGet(); if(tok) h['Authorization']='Bearer '+tok;
  const res=await fetch(API+path,{cache:'no-store',...opts,headers:h});
  const data=await res.json().catch(()=>({}));
  if(res.status===401 && retry && await refreshAccessToken()){
    return api(path,opts,false);
  }
  if(!res.ok) throw new Error(apiErrorMessage(data,'HTTP '+res.status));
  return data;
}

async function uploadFile(input){
  const file=input && input.files && input.files[0];
  if(!file) return '';
  const body=new FormData();
  body.append('file',file);
  const h={};
  const tok=tokenGet(); if(tok) h['Authorization']='Bearer '+tok;
  const res=await fetch(API+'/uploads',{method:'POST',body,headers:h});
  const data=await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(apiErrorMessage(data,'Upload failed'));
  return data.url;
}

function requireAuth(role){
  const u=userGet(); if(!u){location.href=role==='admin'?'/login.html?role=admin':'/login.html';return null}
  const path=location.pathname;
  if(path.startsWith('/dashboard/') && !path.includes('/booking-room.html') && (u.role==='expert'||u.role==='admin')){
    location.href=u.role==='admin'?'/admin/index.html':'/expert/dashboard.html';return null;
  }
  if(path.startsWith('/expert/') && u.role==='user'){
    location.href='/dashboard/index.html';return null;
  }
  if(role==='admin' && u.role!=='admin'){tokenClear();location.href='/login.html?role=admin';return null}
  if(role==='expert' && u.role!=='expert' && u.role!=='admin'){location.href='/dashboard/index.html';return null}
  return u;
}

async function logout(){
  try{await api('/auth/logout',{method:'POST'},false)}catch{}
  tokenClear();location.href='/login.html'
}

function renderNav(){
  const u=userGet();
  const isConsultant=u && (u.role === 'expert' || u.role === 'admin');
  const featureLinks = u && !isConsultant ? `<li><a href="/services.html">Services</a></li>
       <li><a href="/experts.html">Experts</a></li>` : '';
  const pricingLink = !isConsultant ? `<li><a href="/pricing.html">Pricing</a></li>` : '';
  const dashboardHref = u && u.role==='admin' ? '/admin/index.html' : (isConsultant ? '/expert/dashboard.html' : '/dashboard/index.html');
  const right = u
    ? `<button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">Theme</button>
       <button class="btn btn-ghost" onclick="location.href='${dashboardHref}'">Dashboard</button>
       <button class="btn btn-primary" onclick="logout()">Logout</button>`
    : `<button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme">Theme</button>
       <button class="btn btn-ghost" onclick="location.href='/login.html?role=user'">User login</button>
       <button class="btn btn-ghost" onclick="location.href='/login.html?role=consultant'">Consultant login</button>
       <button class="btn btn-ghost" onclick="location.href='/login.html?role=admin'">Admin login</button>
       <button class="btn btn-primary" onclick="location.href='/register.html'">Get Started</button>`;
  document.body.insertAdjacentHTML('afterbegin', `
  <nav>
    <div class="nav-logo" style="cursor:pointer" onclick="location.href='/index.html'">On<span>Cons</span></div>
    <ul class="nav-links">
      <li><a href="/index.html">Home</a></li>
      ${featureLinks}
      ${pricingLink}
      <li><a href="/about.html">About</a></li>
      <li><a href="/contact.html">Contact</a></li>
    </ul>
    <div class="nav-cta">${right}</div>
  </nav>`);
}
function renderFooter(){
  document.body.insertAdjacentHTML('beforeend',`
  <footer>
    <div style="margin-bottom:10px">
      <a href="/about.html">About</a> | <a href="/pricing.html">Pricing</a> | <a href="/faq.html">FAQ</a> | 
      <a href="/reviews.html">Reviews</a> | <a href="/contact.html">Contact</a> | 
      <a href="/privacy-policy.html">Privacy</a> | <a href="/terms.html">Terms</a>
    </div>
    (c) ${new Date().getFullYear()} OnCons - Expert consultation, anytime.
  </footer>`);
}
document.addEventListener('DOMContentLoaded',()=>{
  applyTheme();
  if(location.pathname.startsWith('/admin/')) document.body.classList.add('admin-page');
  if(location.pathname.startsWith('/admin/')) { document.body.insertAdjacentHTML('beforeend','<button class="theme-fab" onclick="toggleTheme()" title="Toggle theme">Theme</button>'); return; }
  if(location.pathname.startsWith('/dashboard/')) document.body.classList.add('user-page');
  if(location.pathname.startsWith('/expert/')) document.body.classList.add('expert-page');
  if(location.pathname.startsWith('/dashboard/') || location.pathname.startsWith('/expert/')) document.body.insertAdjacentHTML('beforeend','<button class="theme-fab" onclick="toggleTheme()" title="Toggle theme">Theme</button>');
  if(!document.body.dataset.noChrome){renderNav();renderFooter()}
});
