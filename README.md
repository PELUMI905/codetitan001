# CodeTitan Travel — Full-stack project

This project keeps the original travel-site imagery and styling and adds a React frontend, a FastAPI backend, and a local SQLite database.

## Included features

- Responsive React/Vite travel website based on the supplied HTML/CSS site.
- Destination list and search loaded from the API/database.
- User registration and sign-in with hashed passwords and signed bearer tokens.
- Authenticated booking requests, personal booking history, and cancellation of pending requests.
- Newsletter subscription storage.
- Admin API endpoints for managing destinations and viewing bookings.
- Interactive API documentation at `/docs`.

**Important:** Destination prices are sample guide prices, and a booking is a request only. The project does not issue airline tickets, confirm hotel availability, or process payments.

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer and npm
- Internet connection for the first `npm install` and Python package installation

## Run the backend (Windows / VS Code)

1. Open a terminal in the `backend` folder:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy .env.example .env
   ```
2. Open `backend/.env` and replace `CODETITAN_SECRET_KEY` with a long random secret. To enable admin endpoints, set a unique `ADMIN_EMAIL` and an `ADMIN_PASSWORD` of at least 12 characters. Keep `.env` private.
3. Start the API:
   ```powershell
   uvicorn main:app --reload
   ```
4. Check `http://127.0.0.1:8000/api/health`. API docs: `http://127.0.0.1:8000/docs`.

The SQLite database is created automatically at `backend/data/codetitan_travel.db` on first startup, with sample destinations. Keep the database file if you want to keep your local accounts and booking requests.

## Run the frontend

Keep the backend running in its own terminal. Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The frontend defaults to `http://127.0.0.1:8000` for the API. To use a different API address, create `frontend/.env` with:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Restart Vite after changing environment variables.

## Admin API

If the `.env` file contains both `ADMIN_EMAIL` and `ADMIN_PASSWORD` before the first backend start, the app creates an administrator account (or promotes the matching existing account). Sign in through the website with those credentials to receive an admin token. The admin endpoints can be tested in `/docs` using the **Authorize** button and `Bearer <token>`:

- `GET /api/admin/bookings`
- `POST /api/admin/destinations`
- `PUT /api/admin/destinations/{destination_id}`
- `DELETE /api/admin/destinations/{destination_id}` (soft-hides the destination)

The current React UI provides customer booking tools; admin operations are API endpoints, not a visual admin dashboard yet.

## API overview

- `GET /api/health`
- `GET /api/destinations?q=paris`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me` (requires bearer token)
- `POST /api/bookings` (requires bearer token)
- `GET /api/bookings/me` (requires bearer token)
- `PATCH /api/bookings/{id}/cancel` (requires bearer token)
- `POST /api/newsletter`

## Security notes

This is a learning/development starter. Before deploying publicly, configure a strong secret, HTTPS, proper production hosting, database backups, rate limiting, email verification/password reset, and a privacy policy. Do not commit `.env`, passwords, tokens, or the SQLite database to GitHub.
"# codetitan001" 
