# URL Shortener

A simple and fast URL shortener service built with Flask and Supabase. Supports custom aliases, folders, tags, click tracking, QR code generation, file uploads, and a dashboard.

## Features

- Shorten URLs with optional custom aliases
- Organize URLs by folders and tags
- Track clicks and access statistics
- Generate QR codes for short URLs
- Upload files with size and type restrictions
- Dashboard for managing URLs
- Rate limiting and session security
- RESTful API endpoints

## Technology Stack

- Python 3
- Flask
- Supabase (PostgreSQL backend)
- QR Code generation with `qrcode` library
- Frontend templates with Jinja2
- Gunicorn for production server

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Mayukhjain24/url.git
   cd url-shortener
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `example.env` to `.env`
   - Fill in your Supabase URL, Supabase Key, and Flask secret key

## Environment Variables

| Variable       | Description                      |
| -------------- | --------------------------------|
| SUPABASE_URL   | Your Supabase project URL        |
| SUPABASE_KEY   | Your Supabase API key            |
| SECRET_KEY     | Flask secret key for sessions   |
| FLASK_ENV      | Set to `production` in production|

## Running Locally

```bash
flask run
```

The app will be available at `http://localhost:5000`.

## Deployment

This app can be deployed on platforms like Heroku or Render.

### Heroku Deployment

1. Create a Heroku app.
2. Set environment variables in Heroku config.
3. Use Gunicorn as the web server:
   ```bash
   gunicorn app:app
   ```
4. Push your code to Heroku remote and deploy.

### Render Deployment

1. Create a new Web Service on Render.
2. Connect your GitHub repository.
3. Set environment variables in Render dashboard.
4. Use the start command:
   ```bash
   gunicorn app:app
   ```

## API Endpoints

- `POST /api/shorten` - Shorten a URL
- `GET /<short_code>` - Redirect to original URL
- `GET /api/urls/stats/<short_code>` - Get URL stats
- `GET /api/urls/list` - List URLs with optional filters
- `GET /qr/<short_code>` - Get QR code image
- `POST /api/upload` - Upload a file

## License

MIT License
