import type { NextApiRequest, NextApiResponse } from 'next';

// proxies requests to the FastAPI backend. Set BACKEND_URL in .env.local or default to localhost
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  try {
    const response = await fetch(`${BACKEND_URL}/recommendations/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
    });
    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (err: any) {
    console.error('proxy error', err);
    return res.status(500).json({ detail: 'failed to contact backend' });
  }
}
