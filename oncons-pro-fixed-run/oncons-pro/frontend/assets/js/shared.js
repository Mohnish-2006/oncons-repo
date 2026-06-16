// shared.js — nav, auth helpers, API client
const API = window.ONCONS_API || (
  location.hostname && !['localhost','127.0.0.1'].includes(location.hostname)
    ? `${location.protocol}//${location.hostname}:8000/api`
    : 'http://localhost:8000/api'
);

function tokenGet(){return localStorage.getItem('oncons_token')}
function tokenSet(t){localStorage.setItem('oncons_token',t)}
function tokenClear(){localStorage.removeItem('oncons_token');localStorage.removeItem('oncons_user')}
function userGet(){try{return JSON.parse(localStorage.getItem('oncons_user'))}catch{return null}}
function userSet(u){localStorage.setItem('oncons_user',JSON.stringify(u))}

async function api(path,opts={}){
  const h={'Content-Type':'application/json',...(opts.headers||{})};
  const tok=tokenGet(); if(tok) h['Authorization']='Bearer '+tok;
  const res=await fetch(API+path,{cache:'no-store',...opts,headers:h});
  const data=await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail||data.message||('HTTP '+res.status));
  return data;
}

function requireAuth(role){
  const u=userGet(); if(!u){location.href='/login.html';return null}
  if(role && u.role!==role && u.role!=='admin'){location.href='/dashboard/index.html';return null}
  return u;
}

function logout(){tokenClear();location.href='/login.html'}

function renderNav(){
  const u=userGet();
  const featureLinks = u
    ? `<li><a href="/services.html">Services</a></li>
       <li><a href="/experts.html">Experts</a></li>`
    : '';
  const right = u
    ? `<button class="btn btn-ghost" onclick="location.href='/dashboard/index.html'">Dashboard</button>
       <button class="btn btn-primary" onclick="logout()">Logout</button>`
    : `<button class="btn btn-ghost" onclick="location.href='/login.html'">Sign in</button>
       <button class="btn btn-primary" onclick="location.href='/register.html'">Get Started</button>`;
  document.body.insertAdjacentHTML('afterbegin', `
  <nav>
    <div class="nav-logo" style="cursor:pointer" onclick="location.href='/index.html'">On<span>Cons</span></div>
    <ul class="nav-links">
      <li><a href="/index.html">Home</a></li>
      ${featureLinks}
      <li><a href="/pricing.html">Pricing</a></li>
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
      <a href="/about.html">About</a>·<a href="/pricing.html">Pricing</a>·<a href="/faq.html">FAQ</a>·
      <a href="/reviews.html">Reviews</a>·<a href="/contact.html">Contact</a>·
      <a href="/privacy-policy.html">Privacy</a>·<a href="/terms.html">Terms</a>
    </div>
    © ${new Date().getFullYear()} OnCons — Expert consultation, anytime.
  </footer>`);
}
document.addEventListener('DOMContentLoaded',()=>{
  if(location.pathname.startsWith('/admin/')) document.body.classList.add('admin-page');
  if(location.pathname.startsWith('/admin/')) return;
  if(location.pathname.startsWith('/dashboard/')) document.body.classList.add('user-page');
  if(!document.body.dataset.noChrome){renderNav();renderFooter()}
});
