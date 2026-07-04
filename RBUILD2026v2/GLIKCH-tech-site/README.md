# GLIKCH.tech Website Scaffold

A separate public-facing website scaffold for **GLIKCH CyberSec & Engineering LLC**. This is isolated from the GLIKCH NEXUZ chatbot/memory console so the business site can ship without destabilizing the local LLM tool.

## What is included

- React + TypeScript + Vite frontend
- Express backend API
- Seeded JSON data store for immediate local use
- Future SQL schema in `server/db/schema.sql`
- Home, Products, Services, GKEDU, How We Work, Support, and Admin/Login screens
- Product sorting, filters, and view modes
- Service booking modal that queues requests for `support@glikch.tech`
- Contact form, FAQ accordion, open/closed hours widget
- Backend-only test auth scaffold

## Run locally

```powershell
npm install
npm run dev
```

Frontend: `http://localhost:5173`
API: `http://localhost:4177`

## Local test auth

Credentials are validated by the backend, not the frontend.

```env
ADMIN_USERNAME=glikch
ADMIN_PASSWORD=REG01$
```

Before production, replace the dev auth with hashed passwords, MFA, database-backed sessions, rate limiting, and HTTPS-only cookies behind Nginx.

## DevSecOps notes

- Inputs are trimmed, length-limited, and control characters are removed server-side.
- Auth and request submission happen through backend endpoints.
- Security headers are set in Express.
- The JSON store is only a scaffold. Move to PostgreSQL or MongoDB before serious production use.
- Add server-side rate limiting and email provider integration before public launch.
