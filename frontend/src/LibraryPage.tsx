import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getLibrary, type LibraryItem } from './api'

type Filter = 'all' | 'info_block' | 'drawing'

export function LibraryPage() {
  const [items, setItems] = useState<LibraryItem[]>([])
  const [counts, setCounts] = useState({ info_block: 0, drawing: 0 })
  const [filter, setFilter] = useState<Filter>('all')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getLibrary()
      .then((data) => {
        setItems(data.items)
        setCounts(data.counts)
      })
      .catch((err) => setError(err.message))
  }, [])

  const visible = useMemo(() => {
    if (filter === 'all') return items
    return items.filter((item) => item.kind === filter)
  }, [items, filter])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-mark">
            SHEET<span>SENSE</span>
          </Link>
          <div className="brand-sub">Segment library</div>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" to="/">
            Drawings
          </Link>
        </div>
      </header>

      <div className="section-head">
        <div>
          <h2>Saved segments</h2>
          <p>
            Taught regions are stored as JPG files in <code>Info Block</code> and{' '}
            <code>Drawing</code> folders.
          </p>
        </div>
      </div>

      <div className="pill-row" style={{ marginBottom: 18 }}>
        <button className={`pill${filter === 'all' ? ' on' : ''}`} onClick={() => setFilter('all')}>
          All · {counts.info_block + counts.drawing}
        </button>
        <button
          className={`pill${filter === 'info_block' ? ' on' : ''}`}
          onClick={() => setFilter('info_block')}
        >
          Info Block · {counts.info_block}
        </button>
        <button
          className={`pill${filter === 'drawing' ? ' on' : ''}`}
          onClick={() => setFilter('drawing')}
        >
          Drawing · {counts.drawing}
        </button>
      </div>

      {error && <div className="empty">{error}</div>}

      {!error && visible.length === 0 && (
        <div className="empty">
          No segments yet. Teach a drawing and save — JPGs appear here automatically.
        </div>
      )}

      <div className="drawing-grid">
        {visible.map((item) => (
          <article key={item.id} className="drawing-card">
            <div className="drawing-thumb">
              <img src={item.url} alt={item.filename} />
            </div>
            <div className="drawing-meta">
              <h3>{item.filename}</h3>
              <p>
                {item.folder} · from {item.source_filename} · page {item.page_index + 1}
              </p>
              <div className="pill-row">
                <span className="pill on">{item.folder}</span>
                <Link className="pill" to={`/teach/${item.page_id}`}>
                  Open sheet
                </Link>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
