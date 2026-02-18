# Manga Recs Frontend

This directory contains a simple Next.js (React) application that provides a UI for the Manga Recommendation API.

## Getting started

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Run development server**
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:3000`.

3. **Backend API**

   The frontend expects the recommendation API to be running separately (FastAPI server).
   By default it proxies through `http://localhost:8000` via the built-in Next.js API route, but you can override with an environment variable:

   ```bash
   echo "BACKEND_URL=http://localhost:8000" > .env.local
   ```

4. **Build for production**
   ```bash
   npm run build
   npm start
   ```

## Features

- Search for a manga title
- Specify how many similar titles to return (Top N)
- Displays results with similarity score, description, and tags

> ⚠️ Make sure CORS is configured correctly on the FastAPI backend if you bypass the proxy.
