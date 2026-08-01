import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  downloadInfoBlockExcel,
  getInfoBlockRows,
  getLibrary,
  listDrawingOcrRuns,
  runDrawingOcr,
  runInfoBlockOcr,
  type DrawingOcrRun,
  type InfoBlockRow,
  type LibraryItem,
} from './api'

type Filter = 'all' | 'info_block' | 'drawing'

export function LibraryPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<LibraryItem[]>([])
  const [counts, setCounts] = useState({ info_block: 0, drawing: 0 })
  const [filter, setFilter] = useState<Filter>('all')
  const [rows, setRows] = useState<InfoBlockRow[]>([])
  const [fieldHeaders, setFieldHeaders] = useState<string[]>([])
  const [drawingRuns, setDrawingRuns] = useState<DrawingOcrRun[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    const [library, info, drawings] = await Promise.all([
      getLibrary(),
      getInfoBlockRows(),
      listDrawingOcrRuns(),
    ])
    setItems(library.items)
    setCounts(library.counts)
    setRows(info.rows)
    setFieldHeaders(info.field_headers)
    setDrawingRuns(drawings.runs)
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message))
  }, [])

  const visible = useMemo(() => {
    if (filter === 'all') return items
    return items.filter((item) => item.kind === filter)
  }, [items, filter])

  async function onOcr() {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const result = await runInfoBlockOcr()
      setRows(result.all_rows)
      const maxFields = Math.max(0, ...result.all_rows.map((row) => row.field_count))
      setFieldHeaders(Array.from({ length: maxFields }, (_, i) => `Field${i + 1}`))
      setMessage(
        `OCR complete: ${result.processed} Info Block${result.processed === 1 ? '' : 's'} → Field1… columns`,
      )
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'OCR failed')
    } finally {
      setBusy(false)
    }
  }

  async function onExcel() {
    setBusy(true)
    setError(null)
    try {
      await downloadInfoBlockExcel()
      setMessage('Excel downloaded: sheetsense_info_blocks.xlsx')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Excel export failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDrawingOcr() {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const result = await runDrawingOcr()
      setDrawingRuns(result.all_runs)
      setMessage(
        `Drawing pipeline complete: ${result.processed} segment${result.processed === 1 ? '' : 's'}. Open review canvas / download DXF.`,
      )
      await refresh()
      if (result.runs[0]) {
        navigate(result.runs[0].review_url)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Drawing OCR failed')
    } finally {
      setBusy(false)
    }
  }

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

      <section className="panel" style={{ marginBottom: 16 }}>
        <h2>Stream A · Info Block → Excel</h2>
        <p className="help">
          OCR every saved Info Block into generic <code>Field1</code>, <code>Field2</code>, …
          columns, then export an Excel table.
        </p>
        <div className="nav-actions" style={{ marginTop: 14 }}>
          <button className="btn btn-primary" disabled={busy || counts.info_block === 0} onClick={() => void onOcr()}>
            {busy ? 'Working…' : `OCR Info Blocks (${counts.info_block})`}
          </button>
          <button className="btn" disabled={busy || rows.length === 0} onClick={() => void onExcel()}>
            Download Excel
          </button>
        </div>
      </section>

      <section className="panel" style={{ marginBottom: 22 }}>
        <h2>Stream B · Drawing pipeline → DXF</h2>
        <p className="help">
          Drawing image → cleanup/deskew → vector lines → <code>PP-OCRv6</code> annotations →
          circles/arcs/symbols → export DXF. Then open the review canvas to check results.
        </p>
        <div className="nav-actions" style={{ marginTop: 14 }}>
          <button
            className="btn btn-primary"
            disabled={busy || counts.drawing === 0}
            onClick={() => void onDrawingOcr()}
          >
            {busy ? 'Running pipeline…' : `Run Drawing pipeline (${counts.drawing})`}
          </button>
        </div>
        {drawingRuns.length > 0 && (
          <div className="field-list" style={{ marginTop: 14 }}>
            {drawingRuns.map((run) => (
              <div className="field" key={run.id}>
                <label>
                  {run.source_filename} · page {run.page_index + 1} · text {run.item_count}
                  {run.counts ? ` · lines ${run.counts.lines ?? 0}` : ''}
                  {run.status === 'reviewed' ? ' · reviewed' : ' · pending review'}
                </label>
                <div>
                  <Link to={run.review_url}>Open review canvas</Link>
                  {run.dxf_url ? ' · DXF ready' : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {rows.length > 0 && (
        <section style={{ marginBottom: 28 }}>
          <div className="section-head">
            <div>
              <h2>Info Block table</h2>
              <p>{rows.length} row(s) ready for Excel export.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Page</th>
                  {fieldHeaders.map((header) => (
                    <th key={header}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.source_filename}</td>
                    <td>{row.page_index + 1}</td>
                    {fieldHeaders.map((header) => (
                      <td key={header}>{row.fields[header] || ''}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

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
        {visible.map((item) => {
          const drawingRun = drawingRuns.find((run) => run.page_id === item.page_id)
          return (
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
                  {item.kind === 'drawing' && drawingRun && (
                    <Link className="pill" to={drawingRun.review_url}>
                      Review OCR
                    </Link>
                  )}
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {message && (
        <div className="toast" onClick={() => setMessage(null)}>
          {message}
        </div>
      )}
    </div>
  )
}
