import { useState } from 'react';

// AniList descriptions can contain HTML; strip it for clean plain-text display.
function stripHtml(value) {
  if (typeof value !== 'string') return value;
  return value.replace(/<[^>]*>/g, '').trim();
}

function formatScore(similarity) {
  return typeof similarity === 'number'
    ? `${Math.round(similarity * 100)}% match`
    : similarity;
}

export default function Home() {
  const [title, setTitle] = useState('');
  const [topN, setTopN] = useState(5);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);
    setSearched(true);

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
      <header className="header">
        <h1 className="title">Manga Recommendations</h1>
        <p className="subtitle">
          Enter a manga you like and discover similar titles from AniList.
        </p>
      </header>

      <div className="card">
        <form onSubmit={handleSubmit} className="search-form">
          <div className="field field--grow">
            <label htmlFor="title">Manga title</label>
            <input
              id="title"
              className="input"
              type="text"
              placeholder="e.g. Berserk"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="topN">Results</label>
            <input
              id="topN"
              className="input input--small"
              type="number"
              min={1}
              max={20}
              value={topN}
              onChange={(e) => setTopN(parseInt(e.target.value, 10))}
            />
          </div>
          <button type="submit" className="btn" disabled={loading}>
            {loading ? 'Searching…' : 'Recommend'}
          </button>
        </form>

        {error && <p className="error">{error}</p>}
      </div>

      {results.length > 0 && (
        <section className="results">
          <h2 className="results-heading">Similar titles</h2>
          {results.map((rec) => (
            <article key={rec.id} className="rec-card">
              <div className="rec-card__head">
                <h3 className="rec-card__title">{rec.title}</h3>
                <span className="score">{formatScore(rec.similarity)}</span>
              </div>
              {rec.description && (
                <p className="rec-card__desc">{stripHtml(rec.description)}</p>
              )}
              {rec.tags && (Array.isArray(rec.tags) ? rec.tags.length > 0 : rec.tags) && (
                <div className="tags">
                  {(Array.isArray(rec.tags) ? rec.tags : [rec.tags]).map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </article>
          ))}
        </section>
      )}

      {!loading && searched && !error && results.length === 0 && (
        <p className="empty">No recommendations found. Try another title.</p>
      )}
    </div>
  );
}
