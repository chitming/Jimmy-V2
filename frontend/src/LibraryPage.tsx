import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  composeSheetCanvas,
  downloadDrawingDxf,
  downloadInfoBlockExcel,
  getInfoBlockRows,
  getLibrary,
  listDrawingOcrRuns,
  listSheetCanvases,
  runDrawingOcr,
  runInfoBlockOcr,
  type DrawingOcrRun,
  type InfoBlockRow,
  type LibraryItem,
  type SheetCanvas,
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
  const [sheets, setSheets] = useState<SheetCanvas[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    const [library, info, drawings, canvas] = await Promise.all([
      getLibrary(),
      getInfoBlockRows(),
      listDrawingOcrRuns(),
      listSheetCanvases(),
    ])
    setItems(library.items)
    setCounts(library.counts)
    setRows(info.rows)
    setFieldHeaders(info.field_headers)
    setDrawingRuns(drawings.runs)
    setSheets(canvas.sheets)
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
      setMessage('Excel downloaded: tdr_info_blocks.xlsx')
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
        `Stream B complete: ${result.processed} Drawing file${result.processed === 1 ? '' : 's'} → ${result.processed} DXF. Download when ready.`,
      )
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Drawing pipeline failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDownloadDxf(pageId: string) {
    setBusy(true)
    setError(null)
    try {
      await downloadDrawingDxf(pageId)
      setMessage(`DXF downloaded: ${pageId}.dxf`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'DXF download failed')
    } finally {
      setBusy(false)
    }
  }

  async function onComposeSheet() {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const result = await composeSheetCanvas(undefined, 'landscape')
      setSheets(result.all_sheets)
      setMessage(
        `Sheet canvas ready: ${result.processed} A4 landscape sheet${result.processed === 1 ? '' : 's'}.`,
      )
      if (result.sheets[0]) {
        navigate(result.sheets[0].edit_url)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sheet compose failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-mark" aria-label="Home">
            T<span>DR</span>
          </Link>
          <div className="brand-sub">Technical Drawing Reader · Segment library</div>
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
          One Drawing file → one loop → one DXF:{' '}
          cleanup/deskew → raster-to-vector lines → PaddleOCR annotations →
          circles/arcs/symbols → DXF.
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
                  {run.segment_filename} · 1 DXF
                  {run.counts ? ` · lines ${run.counts.lines ?? 0}` : ''}
                  {run.counts ? ` · text ${run.counts.texts ?? run.item_count ?? 0}` : ''}
                  {run.counts ? ` · circles ${run.counts.circles ?? 0}` : ''}
                  {run.counts ? ` · symbols ${run.counts.symbols ?? 0}` : ''}
                </label>
                <div className="nav-actions">
                  {run.preview_url ? (
                    <a href={run.preview_url} target="_blank" rel="noreferrer">
                      Preview
                    </a>
                  ) : null}
                  {run.dxf_url ? (
                    <button
                      className="btn"
                      disabled={busy}
                      onClick={() => void onDownloadDxf(run.page_id)}
                    >
                      Download DXF
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel" style={{ marginBottom: 22 }}>
        <h2>Sheet canvas · working space</h2>
        <p className="help">
          Put Stream A + Stream B results back onto one <strong>A4 landscape</strong> sheet
          (horizontal by default). Open the working canvas to move items and edit text.
          More tools come later.
        </p>
        <div className="nav-actions" style={{ marginTop: 14 }}>
          <button
            className="btn btn-primary"
            disabled={busy || (rows.length === 0 && drawingRuns.length === 0)}
            onClick={() => void onComposeSheet()}
          >
            {busy ? 'Composing…' : 'Compose A4 sheet canvas'}
          </button>
        </div>
        {sheets.length > 0 && (
          <div className="field-list" style={{ marginTop: 14 }}>
            {sheets.map((sheet) => (
              <div className="field" key={sheet.id}>
                <label>
                  {sheet.title} · A4 {sheet.paper.orientation} · {sheet.elements.length} items
                </label>
                <div>
                  <Link to={sheet.edit_url}>Open working canvas</Link>
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
                  {item.kind === 'drawing' && drawingRun?.dxf_url && (
                    <button
                      className="pill"
                      disabled={busy}
                      onClick={() => void onDownloadDxf(item.page_id)}
                    >
                      Download DXF
                    </button>
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
