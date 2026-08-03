import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getStats, listDrawings, uploadDrawing, type Drawing, type Stats } from './api'

export function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  async function refresh() {
    const [s, d] = await Promise.all([getStats(), listDrawings()])
    setStats(s)
    setDrawings(d.drawings)
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message))
  }, [])

  async function onUpload(file: File) {
    setBusy(true)
    setError(null)
    try {
      const result = await uploadDrawing(file)
      await refresh()
      if (result.pages[0]) {
        navigate(`/teach/${result.pages[0].id}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-mark" aria-label="Home">
            SHEET<span>SENSE</span>
          </Link>
          <div className="brand-sub">Technical drawing layout teacher</div>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" to="/library">
            Open Segment library
          </Link>
          <button className="btn btn-primary" disabled={busy} onClick={() => inputRef.current?.click()}>
            {busy ? 'Uploading…' : 'Upload Drawing'}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void onUpload(file)
              e.target.value = ''
            }}
          />
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <h1>
            SHEET<span>SENSE</span>
          </h1>
          <p>
            Teach the machine where the information block and drawing canvas live. After a few examples,
            it starts proposing the layout for the next sheet.
          </p>
          <div className="hero-cta">
            <button className="btn btn-primary" disabled={busy} onClick={() => inputRef.current?.click()}>
              Upload Drawing
            </button>
            <Link className="btn btn-ghost" to="/library">
              Open Segment library
            </Link>
          </div>
        </div>
        <aside className="hero-panel">
          <div className="stat-grid">
            <div className="stat-card">
              <strong>{stats?.drawings ?? 0}</strong>
              <span>Drawings uploaded</span>
            </div>
            <div className="stat-card">
              <strong>{stats?.labeled ?? 0}</strong>
              <span>Pages taught</span>
            </div>
            <div className="stat-card">
              <strong>{stats?.info_block_segments ?? 0}</strong>
              <span>Info Block JPGs</span>
            </div>
            <div className="stat-card">
              <strong>{stats?.drawing_segments ?? 0}</strong>
              <span>Drawing JPGs</span>
            </div>
          </div>
        </aside>
      </section>

      <section id="library">
        <div className="section-head">
          <div>
            <h2>Drawing library</h2>
            <p>Open a page to teach the two regions, then extract the information block.</p>
          </div>
        </div>

        {error && <div className="empty">{error}</div>}

        {!error && drawings.length === 0 && (
          <div className="empty">No drawings yet. Upload a vector PDF or JPG to begin teaching.</div>
        )}

        <div className="drawing-grid">
          {drawings.map((drawing) => {
            const first = drawing.pages[0]
            return (
              <Link
                key={drawing.id}
                className="drawing-card"
                to={first ? `/teach/${first.id}` : '/'}
              >
                <div className="drawing-thumb">
                  {first ? <img src={first.image_url} alt="" /> : <span>No page</span>}
                </div>
                <div className="drawing-meta">
                  <h3>{drawing.filename}</h3>
                  <p>
                    {drawing.source_type.toUpperCase()} · {drawing.page_count} page
                    {drawing.page_count === 1 ? '' : 's'}
                  </p>
                  <div className="pill-row">
                    {drawing.pages.map((page) => (
                      <span
                        key={page.id}
                        className={`pill${page.has_annotation ? ' on' : ''}`}
                      >
                        p{page.page_index + 1}
                        {page.has_extraction ? ' · read' : page.has_annotation ? ' · taught' : ''}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </section>
    </div>
  )
}
