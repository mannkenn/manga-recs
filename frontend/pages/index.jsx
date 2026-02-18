import { useState } from 'react';

// component state will hold whatever shape the backend returns, so tags
// might be an array or a string. We'll normalise when rendering.

export default function Home() {
  const [title, setTitle] = useState('');
  const [topN, setTopN] = useState(5);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const res = await fetch('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, top_n: topN }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to get recommendations');
      }
      const data = await res.json();
      setResults(data.recommendations);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>Manga Recommendations</h1>
      <form onSubmit={handleSubmit} style={{ marginBottom: '1.5rem' }}>
        <div style={{ marginBottom: '0.5rem' }}>
          <label htmlFor="title">Title:</label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
          />
        </div>
        <div style={{ marginBottom: '0.5rem' }}>
          <label htmlFor="topN">Top N:</label>
          <input
            id="topN"
            type="number"
            min={1}
            value={topN}
            onChange={(e) => setTopN(parseInt(e.target.value, 10))}
            style={{ width: '4rem', marginLeft: '0.5rem' }}
          />
        </div>
        <button type="submit" disabled={loading} style={{ padding: '0.5rem 1rem' }}>
          {loading ? 'Searching...' : 'Get Recommendations'}
        </button>
      </form>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {results.length > 0 && (
        <div>
          <h2>Results</h2>
          <ul>
            {results.map((rec) => (
              <li key={rec.id} style={{ marginBottom: '1rem' }}>
                <strong>{rec.title}</strong> ({
                  // convert 0‑1 decimal score to percent string
                  typeof rec.similarity === 'number'
                    ? Math.round(rec.similarity * 100)
                    : rec.similarity
                }%)
                <p>{rec.description}</p>
                {rec.tags && (
                  <p>
                    <em>
                      Tags: {Array.isArray(rec.tags) ? rec.tags.join(', ') : rec.tags}
                    </em>
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
