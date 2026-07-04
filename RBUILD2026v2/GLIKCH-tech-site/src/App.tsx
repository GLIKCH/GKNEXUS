import { FormEvent, useEffect, useMemo, useState } from 'react';

type Page = 'home' | 'products' | 'services' | 'gkedu' | 'how' | 'support' | 'admin';
type View = 'small' | 'medium' | 'detailed' | 'grid';
type Product = { id: string; title: string; description: string; price: number; rating: number; category: string; brand: string; type: string; availability: string; featured: boolean; image: string; tags: string[] };
type Service = { id: string; title: string; shortDescription: string; icon: string; image: string };
type FAQ = { id: string; question: string; answer: string; sortOrder: number };
type Step = { id: string; title: string; body: string };
type Data = { products: Product[]; services: Service[]; faqs: FAQ[]; banners: Array<{ title: string; body: string }>; process: Step[] };
const empty: Data = { products: [], services: [], faqs: [], banners: [], process: [] };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Request failed: ${res.status}`);
  return body as T;
}

export default function App() {
  const [page, setPage] = useState<Page>('home');
  const [data, setData] = useState<Data>(empty);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [user, setUser] = useState<{ username: string; admin: number } | null>(null);
  const [loginOpen, setLoginOpen] = useState(false);

  useEffect(() => {
    api<Data>('/api/bootstrap').then(setData).catch((err) => setError(err.message)).finally(() => setLoading(false));
    api<{ user: { username: string; admin: number } | null }>('/api/session').then((res) => setUser(res.user)).catch(() => setUser(null));
  }, []);

  async function logout() {
    await api('/api/logout', { method: 'POST' });
    setUser(null);
    setPage('home');
  }

  const screen = loading ? <Panel>Booting GLIKCH.tech content matrix...</Panel> : error ? <Panel error>{error}</Panel> : (
    page === 'products' ? <Products products={data.products} /> :
    page === 'services' ? <Services services={data.services} /> :
    page === 'gkedu' ? <GKEDU /> :
    page === 'how' ? <HowWeWork steps={data.process} /> :
    page === 'support' ? <Support faqs={data.faqs} /> :
    page === 'admin' ? <Admin user={user} /> :
    <Home data={data} go={setPage} />
  );

  return <div className="app"><div className="scan" aria-hidden="true" /><Header page={page} setPage={setPage} user={user} onLogin={() => setLoginOpen(true)} onLogout={logout} />{screen}<Footer go={setPage} />{loginOpen && <Login onClose={() => setLoginOpen(false)} onUser={setUser} />}</div>;
}

function Header({ page, setPage, user, onLogin, onLogout }: { page: Page; setPage: (p: Page) => void; user: { admin: number } | null; onLogin: () => void; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const items: Array<[Page, string]> = [['home','Home'], ['products','Products'], ['services','Services'], ['gkedu','GKEDU'], ['how','How We Work'], ['support','Support']];
  if (user?.admin) items.push(['admin', 'Admin']);
  const go = (p: Page) => { setPage(p); setOpen(false); };
  return <header className="header"><button className="brand" onClick={() => go('home')}><span className="brandmark">G</span><span><b>GLIKCH.tech</b><small>CyberSec & Engineering LLC</small></span></button><button className="hamb" onClick={() => setOpen(!open)}>Menu</button><nav className={open ? 'nav open' : 'nav'}>{items.map(([key,label]) => <button key={key} className={page === key ? 'active' : ''} onClick={() => go(key)}>{label}</button>)}</nav><button className="ghost" onClick={user ? onLogout : onLogin}>{user ? 'Logout' : 'Login'}</button></header>;
}

function Home({ data, go }: { data: Data; go: (p: Page) => void }) {
  return <main className="page"><section className="hero"><div><p className="eyebrow">GLIKCH CyberSec & Engineering LLC</p><h1>Cybersecurity, software, hardware, and nerd-grade gear for people who still believe technology should feel powerful.</h1><p>Tech support from the timeline where the arcade kid became the cybersecurity engineer.</p><div className="actions"><button className="primary" onClick={() => go('services')}>Book a Service</button><button className="ghost" onClick={() => go('products')}>Browse Products</button></div></div><img src="/assets/placeholder.svg" alt="Retro cyber workstation" /></section><CTA title="Repair. Build. Secure. Automate." body="No floppy disk required. GLIKCH blends practical tech support, secure builds, education, and future-ready automation." go={go} /><section className="grid"><Heading eyebrow="Service Teasers" title="Fast scan. Click for the full briefing." />{data.services.slice(0,3).map(s => <Card key={s.id} img={s.image} title={s.title} body={s.shortDescription} action="Click to Learn More" onClick={() => go('services')} />)}</section><section className="grid"><Heading eyebrow="Featured Catalog" title="Gear, courses, books, and future affiliate lanes." />{data.products.filter(p => p.featured).slice(0,3).map(p => <Card key={p.id} img={p.image} title={p.title} body={p.description} action="View Product" onClick={() => go('products')} />)}</section></main>;
}

function Products({ products }: { products: Product[] }) {
  const [category, setCategory] = useState('all'), [type, setType] = useState('all'), [availability, setAvailability] = useState('all'), [rating, setRating] = useState(0), [maxPrice, setMaxPrice] = useState(250), [sort, setSort] = useState('featured'), [view, setView] = useState<View>('grid');
  const visible = useMemo(() => products.filter(p => (category === 'all' || p.category === category) && (type === 'all' || p.type === type) && (availability === 'all' || p.availability === availability) && p.rating >= rating && p.price <= maxPrice).sort((a,b) => sort === 'price-asc' ? a.price-b.price : sort === 'price-desc' ? b.price-a.price : sort === 'rating' ? b.rating-a.rating : Number(b.featured)-Number(a.featured)), [products, category, type, availability, rating, maxPrice, sort]);
  return <main className="page"><Title eyebrow="Products" title="Cyberpunk NewEgg meets nerdy field shop." body="GLIKCH products, education, hardware, books, merch, electronics, and affiliate-ready catalog structure." /><div className="catalog"><aside className="panel filters"><h2>Filters</h2><Select label="Category" value={category} set={setCategory} options={uniq(products.map(p => p.category))} /><Select label="Type" value={type} set={setType} options={uniq(products.map(p => p.type))} /><Select label="Availability" value={availability} set={setAvailability} options={uniq(products.map(p => p.availability))} /><label>Minimum Rating<select value={rating} onChange={e => setRating(Number(e.target.value))}><option value="0">Any</option><option value="4">4+</option><option value="4.5">4.5+</option></select></label><label>Max Price: ${maxPrice}<input type="range" min="10" max="250" value={maxPrice} onChange={e => setMaxPrice(Number(e.target.value))} /></label></aside><section><div className="toolbar"><b>{visible.length} result(s)</b><select value={sort} onChange={e => setSort(e.target.value)}><option value="featured">Featured</option><option value="price-asc">Price Low to High</option><option value="price-desc">Price High to Low</option><option value="rating">Star Rating</option></select><div className="views">{(['small','medium','detailed','grid'] as View[]).map(v => <button key={v} className={view === v ? 'active' : ''} onClick={() => setView(v)}>{v}</button>)}</div></div><div className={`products ${view}`}>{visible.map(p => <ProductCard key={p.id} product={p} view={view} />)}</div></section></div></main>;
}

function ProductCard({ product, view }: { product: Product; view: View }) {
  return <article className="product card"><img src={product.image} alt="" /><div><span className="tag">{product.category} / {product.type}</span><h3>{product.title}</h3>{view !== 'small' && <p>{product.description}</p>}{view === 'detailed' && <p className="muted">Brand: {product.brand} | Availability: {product.availability} | Tags: {product.tags.join(', ')}</p>}<p className="meta"><b>${product.price.toFixed(2)}</b><span>{product.rating.toFixed(1)} stars</span><span>{product.availability}</span></p><button className="primary">View Details</button></div></article>;
}

function Services({ services }: { services: Service[] }) {
  const [service, setService] = useState<Service | null>(null);
  return <main className="page"><Title eyebrow="Services" title="Full service details live here." body="Professional technology help with the right amount of retro voltage." /><section className="grid services">{services.map(s => <article className="card" key={s.id}><img src={s.image} alt="" /><span className="pill">{s.icon}</span><h2>{s.title}</h2><p>{s.shortDescription}</p><button className="primary" onClick={() => setService(s)}>Book Service</button></article>)}</section>{service && <Booking service={service} close={() => setService(null)} />}</main>;
}

function GKEDU() { return <main className="page"><Title eyebrow="GKEDU" title="Education for builders, defenders, and curious minds." body="Course lanes for coding basics, secure web development, cybersecurity fundamentals, AI workflows, and project-based learning." /><section className="grid">{['Coding Foundations','Cybersecurity Basics','AI Workflow Lab','Hardware & Home Lab'].map(t => <Card key={t} img="/assets/placeholder.svg" title={t} body="Practical projects, plain-English explanations, and security-first habits." action="Join Waitlist" />)}</section></main>; }
function HowWeWork({ steps }: { steps: Step[] }) { return <main className="page"><Title eyebrow="How We Work" title="Clear process. Fewer surprises." body="Each project moves from signal gathering to tested delivery with documentation you can actually read." /><section className="timeline">{steps.map((s,i) => <article className="process card" key={s.id}><img src="/assets/placeholder.svg" alt="" /><span>{String(i+1).padStart(2,'0')}</span><div><h2>{s.title}</h2><p>{s.body}</p></div></article>)}</section></main>; }

function Support({ faqs }: { faqs: FAQ[] }) {
  const [status, setStatus] = useState(''), [err, setErr] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) { e.preventDefault(); setStatus(''); setErr(''); const f = new FormData(e.currentTarget); try { const r = await api<{ message: string }>('/api/contact-requests', { method: 'POST', body: JSON.stringify({ name: f.get('name'), email: f.get('email'), message: f.get('message') }) }); setStatus(r.message); e.currentTarget.reset(); } catch (x) { setErr(x instanceof Error ? x.message : 'Could not send request.'); } }
  return <main className="page"><Title eyebrow="Support" title="Tell GLIKCH what broke, what needs building, or what needs securing." /><div className="support"><form className="panel form" onSubmit={submit}><label>Name<input name="name" required maxLength={100} /></label><label>Email<input name="email" type="email" required maxLength={254} /></label><label className="wide">Message<textarea name="message" required maxLength={3000} rows={6} /></label><button className="primary wide">Send Request</button>{status && <p className="ok wide">{status}</p>}{err && <p className="bad wide">{err}</p>}</form><aside className="stack"><Hours /><article className="panel"><h2>Work Area</h2><p>Primarily online and remote at the moment. Local service focus includes Burnsville, Asheville, NC, and surrounding areas.</p></article><article className="panel"><h2>Custom Requests</h2><p>GLIKCH handles specific client requests depending on project needs, risk, timeline, and available resources.</p></article></aside></div><FAQ faqs={faqs} /></main>;
}

function Admin({ user }: { user: { admin: number } | null }) { if (!user?.admin) return <Panel>Admin access required.</Panel>; return <main className="page"><Title eyebrow="Admin" title="GLIKCH control scaffold." body={`Admin value: ${user.admin}. Ready for protected CRUD screens.`} /><section className="grid">{['Products','Services','FAQs','Contact Requests','Bookings','Banners'].map(x => <article className="panel" key={x}><h2>{x}</h2><p>TODO: connect CRUD routes with role checks, audit logs, and validation.</p></article>)}</section></main>; }

function Booking({ service, close }: { service: Service; close: () => void }) {
  const [status, setStatus] = useState(''), [err, setErr] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) { e.preventDefault(); setStatus('Sending request...'); setErr(''); const f = new FormData(e.currentTarget); try { const r = await api<{ message: string; sendTo: string }>('/api/service-bookings', { method: 'POST', body: JSON.stringify({ name: f.get('name'), email: f.get('email'), phone: f.get('phone'), serviceType: f.get('serviceType'), message: f.get('message') }) }); setStatus(`${r.message} Destination: ${r.sendTo}`); e.currentTarget.reset(); } catch (x) { setStatus(''); setErr(x instanceof Error ? x.message : 'Could not send request.'); } }
  return <div className="modal"><div className="modalcard"><button className="close" onClick={close}>X</button><p className="eyebrow">Book Service</p><h2>{service.title}</h2><form className="form" onSubmit={submit}><label>Name<input name="name" required /></label><label>Email<input name="email" type="email" required /></label><label>Phone<input name="phone" /></label><label>Service<input name="serviceType" defaultValue={service.title} required /></label><label className="wide">Details<textarea name="message" rows={5} required /></label><button className="primary wide">Submit Request</button></form>{status && <p className="ok">{status}</p>}{err && <p className="bad">{err}</p>}</div></div>;
}

function Login({ onClose, onUser }: { onClose: () => void; onUser: (u: { username: string; admin: number }) => void }) {
  const [err, setErr] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) { e.preventDefault(); const f = new FormData(e.currentTarget); try { const r = await api<{ user: { username: string; admin: number } }>('/api/login', { method: 'POST', body: JSON.stringify({ username: f.get('username'), password: f.get('password') }) }); onUser(r.user); onClose(); } catch (x) { setErr(x instanceof Error ? x.message : 'Login failed.'); } }
  return <div className="modal"><div className="modalcard login"><button className="close" onClick={onClose}>X</button><p className="eyebrow">Secure Console</p><h2>Admin Login</h2><form className="form" onSubmit={submit}><label className="wide">Username<input name="username" autoComplete="username" required /></label><label className="wide">Password<input name="password" type="password" autoComplete="current-password" required /></label><button className="primary wide">Enter Console</button></form>{err && <p className="bad">{err}</p>}</div></div>;
}

function FAQ({ faqs }: { faqs: FAQ[] }) { const [open, setOpen] = useState(faqs[0]?.id || ''); return <section className="faq"><h2>FAQ</h2>{faqs.sort((a,b) => a.sortOrder-b.sortOrder).map(f => <article className="accordion" key={f.id}><button onClick={() => setOpen(open === f.id ? '' : f.id)}>{f.question}<span>{open === f.id ? '-' : '+'}</span></button>{open === f.id && <p>{f.answer}</p>}</article>)}</section>; }
function Hours() { const d = new Date(), open = d.getDay() >= 1 && d.getDay() <= 6 && d.getHours() >= 9 && d.getHours() < 18; return <article className={open ? 'panel hours open' : 'panel hours closed'}><p className="eyebrow">Hours</p><h2>{open ? 'Open Signal' : 'Closed Signal'}</h2><p>Monday-Saturday, 9:00 AM-6:00 PM Eastern</p><p>{open ? 'Green light. Send the request.' : 'Red light. Leave a message and GLIKCH will follow up.'}</p></article>; }
function CTA({ title, body, go }: { title: string; body: string; go: (p: Page) => void }) { return <section className="cta"><div><p className="eyebrow">Signal Boost</p><h2>{title}</h2><p>{body}</p></div><button className="primary" onClick={() => go('how')}>See How We Work</button></section>; }
function Card({ img, title, body, action, onClick }: { img: string; title: string; body: string; action: string; onClick?: () => void }) { return <article className="card"><img src={img} alt="" /><h3>{title}</h3><p>{body}</p><button onClick={onClick}>{action}</button></article>; }
function Heading({ eyebrow, title }: { eyebrow: string; title: string }) { return <div className="heading"><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>; }
function Title({ eyebrow, title, body }: { eyebrow: string; title: string; body?: string }) { return <section className="title"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{body && <p>{body}</p>}</section>; }
function Panel({ children, error }: { children: React.ReactNode; error?: boolean }) { return <main className={error ? 'page panel bad' : 'page panel'}>{children}</main>; }
function Select({ label, value, set, options }: { label: string; value: string; set: (v: string) => void; options: string[] }) { return <label>{label}<select value={value} onChange={e => set(e.target.value)}><option value="all">All</option>{options.map(o => <option key={o}>{o}</option>)}</select></label>; }
function uniq(values: string[]) { return Array.from(new Set(values)).sort(); }
function Footer({ go }: { go: (p: Page) => void }) { return <footer className="footer"><div><b>GLIKCH CyberSec & Engineering LLC</b><p>Repair. Build. Secure. Automate. No floppy disk required.</p></div><div><button onClick={() => go('services')}>Book Service</button><button onClick={() => go('products')}>Catalog</button><button onClick={() => go('support')}>Support</button></div></footer>; }
