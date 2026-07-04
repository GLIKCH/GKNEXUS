import express from 'express';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = Number(process.env.PORT || 4177);
const supportEmail = process.env.SUPPORT_EMAIL || 'support@glikch.tech';
const dbPath = path.join(__dirname, 'data', 'db.json');
const sessions = new Map();

app.disable('x-powered-by');
app.use(express.json({ limit: '150kb' }));
app.use((_req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  next();
});

app.get('/api/health', (_req, res) => res.json({ ok: true, service: 'glikch-tech-site', time: new Date().toISOString() }));
app.get('/api/bootstrap', (_req, res) => {
  const db = readDb();
  res.json({ products: db.products, services: db.services, faqs: db.faqs, banners: db.banners, process: db.process });
});
app.get('/api/products', (_req, res) => res.json(readDb().products));
app.get('/api/services', (_req, res) => res.json(readDb().services));
app.get('/api/faqs', (_req, res) => res.json(readDb().faqs));

app.post('/api/contact-requests', (req, res) => {
  const body = sanitizeContact(req.body);
  if (!body.ok) return res.status(400).json({ error: body.error });
  const record = insert('contactRequests', { ...body.value, status: 'new' });
  res.status(201).json({ ok: true, requestId: record.id, message: 'Contact request saved for GLIKCH review.' });
});

app.post('/api/service-bookings', (req, res) => {
  const body = sanitizeBooking(req.body);
  if (!body.ok) return res.status(400).json({ error: body.error });
  const record = insert('serviceBookings', { ...body.value, sendTo: supportEmail, status: 'queued' });
  res.status(201).json({ ok: true, requestId: record.id, sendTo: supportEmail, message: 'Service request queued.' });
});

app.post('/api/login', (req, res) => {
  const username = clean(req.body?.username, 80).toLowerCase();
  const password = String(req.body?.password || '');

  // TODO: Replace this dev-only auth with hashed passwords, MFA, rate limiting,
  // audit logging, and database-backed sessions before public production use.
  const expectedUser = (process.env.ADMIN_USERNAME || 'glikch').toLowerCase();
  const expectedPass = process.env.ADMIN_PASSWORD || 'REG01$';
  if (username !== expectedUser || password !== expectedPass) return res.status(401).json({ error: 'Invalid username or password.' });

  const token = crypto.randomBytes(32).toString('hex');
  sessions.set(token, { username, admin: 1, createdAt: Date.now() });
  res.setHeader('Set-Cookie', `glikch_session=${token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800`);
  res.json({ ok: true, user: { username, admin: 1 } });
});

app.post('/api/logout', (req, res) => {
  const token = cookie(req, 'glikch_session');
  if (token) sessions.delete(token);
  res.setHeader('Set-Cookie', 'glikch_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0');
  res.json({ ok: true });
});

app.get('/api/session', (req, res) => {
  const session = sessions.get(cookie(req, 'glikch_session')) || null;
  res.json({ authenticated: Boolean(session), user: session ? { username: session.username, admin: session.admin } : null });
});

const dist = path.resolve(__dirname, '..', 'dist');
if (process.env.NODE_ENV === 'production' && fs.existsSync(dist)) {
  app.use(express.static(dist));
  app.use((req, res, next) => {
    if (req.path.startsWith('/api') || req.method !== 'GET') return next();
    res.sendFile(path.join(dist, 'index.html'));
  });
}

app.listen(port, () => console.log(`GLIKCH.tech API listening on http://localhost:${port}`));

function readDb() {
  ensureDb();
  return JSON.parse(fs.readFileSync(dbPath, 'utf8'));
}

function writeDb(db) {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  fs.writeFileSync(dbPath, JSON.stringify(db, null, 2));
}

function insert(collection, value) {
  const db = readDb();
  const record = { id: `${collection}-${crypto.randomUUID()}`, createdAt: new Date().toISOString(), ...value };
  db[collection] = Array.isArray(db[collection]) ? db[collection] : [];
  db[collection].push(record);
  writeDb(db);
  return record;
}

function ensureDb() {
  if (fs.existsSync(dbPath)) return;
  const seed = JSON.parse(fs.readFileSync(path.join(__dirname, 'db', 'seed.json'), 'utf8'));
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  fs.writeFileSync(dbPath, JSON.stringify(seed, null, 2));
}

function sanitizeContact(input) {
  const value = { name: clean(input?.name, 100), email: email(input?.email), message: clean(input?.message, 3000) };
  if (!value.name || !value.email || !value.message) return { ok: false, error: 'Name, valid email, and message are required.' };
  return { ok: true, value };
}

function sanitizeBooking(input) {
  const value = {
    name: clean(input?.name, 100),
    email: email(input?.email),
    phone: clean(input?.phone, 40),
    serviceType: clean(input?.serviceType, 120),
    message: clean(input?.message, 3000)
  };
  if (!value.name || !value.email || !value.serviceType || !value.message) return { ok: false, error: 'Name, valid email, service type, and details are required.' };
  return { ok: true, value };
}

function clean(value, max) {
  return String(value || '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
}

function email(value) {
  const safe = clean(value, 254).toLowerCase();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(safe) ? safe : '';
}

function cookie(req, name) {
  return (req.headers.cookie || '').split(';').map((part) => part.trim()).find((part) => part.startsWith(`${name}=`))?.split('=')[1] || '';
}

