# Frontend (Vite + React + TypeScript)

Quickstart to run the green UI locally.

Prerequisites
- Node.js 18+ (LTS recommended)
- npm 9+
- Backend running at `http://localhost:8000` (or adjust `VITE_API_BASE`)

Setup
- Copy env: `cp .env.example .env` (Windows PowerShell: `Copy-Item .env.example .env`)
- Edit `.env` if needed:
  - `VITE_API_BASE=http://localhost:8000`

Install & Run (Dev)
- `npm i`
- `npm run dev`
- Open `http://localhost:5173`

Build & Preview
- `npm run build`
- `npm run preview` (serves the built `dist/` locally)

Project Structure
- `src/main.tsx` — App bootstrap, Router + AuthProvider
- `src/App.tsx` — Routes and page layout
- `src/context/AuthContext.tsx` — Auth state, token/role, redirects
- `src/api/client.ts` — Axios client (reads `VITE_API_BASE`)
- `src/api/auth.ts` — `/auth/login`, `/auth/signup`, `/users/me`
- `src/components/*` — TopBar, LeftNav, small UI pieces
- `src/pages/*` — Login, Signup, Citizen/Inspector/Manager views
- `src/styles.css` — Minimal theme/styles matching green palette

Auth & Routing
- Public routes: `/login`, `/signup`
- Role routes:
  - `Citizen` → `/citizen`
  - `Inspector` → `/inspector`
  - `Manager`/`Admin` → `/manager` and `/map`
- Token is stored in `localStorage` and sent as `Authorization: Bearer <token>`

Environment Variables
- `VITE_API_BASE` — Backend base URL (defaults to `http://localhost:8000` if not set)

Troubleshooting
- Blank page → Ensure backend is running and frontend dev server is on `5173`. Check browser console errors.
- 401/403 → Verify you’re logged in; backend reachable; correct `VITE_API_BASE`.
- CORS errors → Backend must allow `http://localhost:5173` (already configured).
- Admin login → Seed admin in backend: `python -m backend.seed_admin`.

Scripts
- `npm run dev` — Vite dev server
- `npm run build` — Production build
- `npm run preview` — Preview build locally

Notes
- MapView is a placeholder; integrate Leaflet/Map provider later.
