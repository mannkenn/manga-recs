import Head from 'next/head';
import { useEffect, useRef, useState } from 'react';

import { fetchHealth, fetchRecommendations } from '../lib/api';

// Cleaning lowercases titles so that fuzzy matching is case-insensitive, which
// means the display copy has to put the capitals back.
const MINOR_WORDS = new Set(['a', 'an', 'and', 'as', 'at', 'by', 'in', 'no', 'of', 'on', 'or', 'the', 'to']);

function titleCase(value) {
  if (typeof value !== 'string') return value;
  return value
    .split(' ')
    .map((word, index) => {
      if (index > 0 && MINOR_WORDS.has(word)) return word;
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
}

function stripHtml(value) {
  if (typeof value !== 'string') return value;
  return value.replace(/<[^>]*>/g, '').trim();
}

const EXAMPLES = ['Berserk', 'Attack on Titan', 'Oyasumi Punpun', 'Vinland Saga', 'Chainsaw Man'];

export default function Home() {
  // Read the catalogue size from the service rather than hardcoding it. The
  // number changes every time the model is retrained, and stale copy claiming a
  // count the API disagrees with is worse than no count at all.
  const [catalogSize, setCatalogSize] = useState(null);
  const [title, setTitle] = useState('');
  const [topN, setTopN] = useState(5);
  const [results, setResults] = useState([]);
  const [matched, setMatched] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);
  const inFlight = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((health) => {
        if (!cancelled && health?.items) setCatalogSize(health.items);
      })
      // Purely decorative: the subtitle just omits the count if this fails.
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const run = async (queryTitle) => {
    const query = (queryTitle ?? title).trim();
    if (!query) return;

    // Abort any previous request so a slow response cannot overwrite a newer one.
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;

    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const data = await fetchRecommendations({ title: query, topN, signal: controller.signal });
      setResults(data.recommendations ?? []);
      setMatched(data.matched_title ?? null);
    } catch (err) {
      if (err.name === 'AbortError') return;
      setError(err.message);
      setResults([]);
      setMatched(null);
    } finally {
      if (inFlight.current === controller) setLoading(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    run();
  };

  const handleExample = (example) => {
    setTitle(example);
    run(example);
  };

  return (
    <div className="container">
      <Head>
        <title>Manga Recommendations</title>
        <meta
          name="description"
          content="Content-based manga recommendations from AniList metadata."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <header className="header">
        <h1 className="title">Manga Recommendations</h1>
        <p className="subtitle">
          Content-based recommendations over {catalogSize ? `${catalogSize.toLocaleString()} ` : ''}
          AniList titles. Similarity is cosine distance across genres, tags, authors, and
          normalised numeric metadata.
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
              onChange={(event) => setTitle(event.target.value)}
              autoComplete="off"
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
              onChange={(event) => setTopN(Math.max(1, Math.min(20, Number(event.target.value) || 1)))}
            />
          </div>
          <button type="submit" className="btn" disabled={loading || !title.trim()}>
            {loading ? 'Searching' : 'Recommend'}
          </button>
        </form>

        <div className="examples">
          <span className="examples__label">Try</span>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="chip"
              onClick={() => handleExample(example)}
              disabled={loading}
            >
              {example}
            </button>
          ))}
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      {results.length > 0 && (
        <section className="results">
          <h2 className="results-heading">
            Similar titles
            {matched && <span className="results-matched"> — matched “{titleCase(matched)}”</span>}
          </h2>

          <ol className="results-list">
            {results.map((rec, index) => (
              <li key={rec.id}>
                <article className="rec-card">
                  <div className="rec-card__head">
                    <h3 className="rec-card__title">
                      <span className="rec-card__rank">{index + 1}</span>
                      {titleCase(rec.title)}
                    </h3>
                    <span className="score" title={`cosine similarity ${rec.similarity}`}>
                      {(rec.similarity * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className="meter" aria-hidden="true">
                    <div
                      className="meter__fill"
                      style={{ width: `${Math.min(100, rec.similarity * 100)}%` }}
                    />
                  </div>

                  {rec.description && (
                    <p className="rec-card__desc">{stripHtml(rec.description)}</p>
                  )}

                  {rec.genres?.length > 0 && (
                    <div className="tags">
                      {rec.genres.map((genre) => (
                        <span key={genre} className="tag tag--genre">
                          {genre}
                        </span>
                      ))}
                    </div>
                  )}

                  {rec.tags?.length > 0 && (
                    <div className="tags">
                      {rec.tags.slice(0, 8).map((tag) => (
                        <span key={tag} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </article>
              </li>
            ))}
          </ol>
        </section>
      )}

      {!loading && searched && !error && results.length === 0 && (
        <p className="empty">No recommendations found. Try another title.</p>
      )}

      <footer className="footer">
        <a href="/docs">API documentation</a>
        <span className="footer__sep">·</span>
        <a href="https://github.com/mannkenn/manga-recs">Source</a>
      </footer>
    </div>
  );
}
