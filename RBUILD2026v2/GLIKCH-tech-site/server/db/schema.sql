-- Future relational schema for GLIKCH.tech. The current scaffold uses JSON storage so the site runs immediately.
CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, email TEXT, admin INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE products (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, price NUMERIC NOT NULL, rating NUMERIC NOT NULL DEFAULT 0, category TEXT NOT NULL, brand TEXT NOT NULL, type TEXT NOT NULL, availability TEXT NOT NULL, featured INTEGER NOT NULL DEFAULT 0, image TEXT, tags TEXT NOT NULL);
CREATE TABLE services (id TEXT PRIMARY KEY, title TEXT NOT NULL, short_description TEXT NOT NULL, icon TEXT, image TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE faqs (id TEXT PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL, category TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0);
CREATE TABLE contact_requests (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new');
CREATE TABLE service_booking_requests (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT, service_type TEXT NOT NULL, message TEXT NOT NULL, send_to TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued');
CREATE TABLE site_banners (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, cta_label TEXT, cta_target TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE content_blocks (id TEXT PRIMARY KEY, page TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, image TEXT, sort_order INTEGER NOT NULL DEFAULT 0);
