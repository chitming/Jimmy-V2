import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  downloadDrawingDxf,
  getDrawingOcr,
  runDrawingOcr,
  saveDrawingOcrReview,
  type DrawingOcrItem,
  type DrawingOcrRun,
} from './api'

export function DrawingReviewPage() {
  const { pageId = '' } = useParams()
  const [run, setRun] = useState<DrawingOcrRun | null>(null)
  const [items, setItems] = useState<DrawingOcrItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    const data = await getDrawingOcr(pageId)
    setRun(data)
    setItems(data.items)
    setSelectedId(data.items[0]?.id ?? null)
    setShowPreview(Boolean(data.preview_url))
  }

  useEffect(() => {
    if (!pageId) return
    setError(null)
    load().catch((err) => setError(err.message))
  }, [pageId])

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  )

  function updateSelectedText(text: string) {
    if (!selectedId) return
    setItems((prev) =>
      prev.map((item) =>
        item.id === selectedId ? { ...item, text, edited: true } : item,
      ),
    )
  }

  async function onRerun() {
    setBusy(true)
    setError(null)
    try {
      await runDrawingOcr(pageId)
      await load()
      setMessage('Drawing pipeline finished. Check vectors + OCR, then download DXF.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pipeline failed')
    } finally {
      setBusy(false)
    }
  }

  async function onSaveReview() {
    setBusy(true)
    setError(null)
    try {
      const saved = await saveDrawingOcrReview(pageId, items, 'reviewed')
      setRun(saved)
      setItems(saved.items)
      setMessage('Review saved. Annotation text confirmed.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDxf() {
    setBusy(true)
    setError(null)
    try {
      await downloadDrawingDxf(pageId)
      setMessage('DXF downloaded.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'DXF download failed')
    } finally {
      setBusy(false)
    }
  }

  if (error && !run) {
    return (
      <div className="app-shell">
        <div className="empty">{error}</div>
        <div className="nav-actions" style={{ marginTop: 16 }}>
          <Link className="btn" to="/library">
            Back to library
          </Link>
          <button className="btn btn-primary" disabled={busy} onClick={() => void onRerun()}>
            Run Drawing pipeline
          </button>
        </div>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="app-shell">
        <div className="empty">Loading Drawing pipeline result…</div>
      </div>
    )
  }

  const canvasUrl = showPreview && run.preview_url ? run.preview_url : run.image_url
  const counts = run.counts || {}

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-mark">
            SHEET<span>SENSE</span>
          </Link>
          <div className="brand-sub">
            Stream B · Drawing pipeline · {run.source_filename}
          </div>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" to="/library">
            Segments
          </Link>
          <button className="btn" disabled={busy} onClick={() => void onRerun()}>
            Re-run pipeline
          </button>
          <button className="btn" disabled={busy || !run.dxf_url} onClick={() => void onDxf()}>
            Download DXF
          </button>
          <button className="btn btn-primary" disabled={busy} onClick={() => void onSaveReview()}>
            Save review
          </button>
        </div>
      </header>

      <div className="workspace review-workspace">
        <aside className="panel">
          <h2>Pipeline</h2>
          <p className="help">
            Drawing image → cleanup/deskew → vector lines → PP-OCRv6 → circles/arcs/symbols → DXF
          </p>
          <div className="field-list" style={{ marginBottom: 12 }}>
            {(run.stages || []).map((stage) => (
              <div className="field" key={stage.id}>
                <label>{stage.ok ? 'OK' : 'Fail'}</label>
                <div>{stage.label}</div>
              </div>
            ))}
          </div>
          <div className={`status-banner${run.status === 'reviewed' ? ' ok' : ''}`}>
            lines {counts.lines ?? 0} · circles {counts.circles ?? 0} · arcs {counts.arcs ?? 0} ·
            symbols {counts.symbols ?? 0} · text {counts.texts ?? items.length}
          </div>

          <div className="nav-actions" style={{ marginBottom: 12 }}>
            <button
              className={`pill${showPreview ? ' on' : ''}`}
              onClick={() => setShowPreview(true)}
              disabled={!run.preview_url}
            >
              Vector preview
            </button>
            <button className={`pill${!showPreview ? ' on' : ''}`} onClick={() => setShowPreview(false)}>
              Original
            </button>
          </div>

          <div className="ocr-list">
            {items.map((item) => (
              <button
                key={item.id}
                className={`ocr-item${selectedId === item.id ? ' active' : ''}`}
                onClick={() => setSelectedId(item.id)}
              >
                <strong>{item.text || '(empty)'}</strong>
                <span>
                  {(item.score * 100).toFixed(0)}%
                  {item.edited ? ' · edited' : ''}
                </span>
              </button>
            ))}
            {items.length === 0 && <p className="help">No annotation text detected.</p>}
          </div>
        </aside>

        <div className="stage-wrap review-stage">
          <div className="stage">
            <img src={canvasUrl} alt="Drawing pipeline review canvas" draggable={false} />
            {!showPreview && (
              <div className="overlay review-overlay">
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`ocr-box${selectedId === item.id ? ' active' : ''}${item.edited ? ' edited' : ''}`}
                    style={{
                      left: `${item.box.x * 100}%`,
                      top: `${item.box.y * 100}%`,
                      width: `${item.box.w * 100}%`,
                      height: `${item.box.h * 100}%`,
                    }}
                    onClick={() => setSelectedId(item.id)}
                    title={item.text}
                  >
                    <span>{item.text}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <aside className="panel">
          <h2>Selected text</h2>
          {!selected && <p className="help">Select an OCR item to inspect or correct it.</p>}
          {selected && (
            <>
              <label className="help" htmlFor="ocr-text-edit">
                Recognized annotation
              </label>
              <textarea
                id="ocr-text-edit"
                className="ocr-edit"
                value={selected.text}
                onChange={(e) => updateSelectedText(e.target.value)}
              />
              <div className="field-list" style={{ marginTop: 12 }}>
                <div className="field">
                  <label>Confidence</label>
                  <div>{(selected.score * 100).toFixed(1)}%</div>
                </div>
                <div className="field">
                  <label>Item</label>
                  <div>{selected.id}</div>
                </div>
              </div>
            </>
          )}
          <p className="help" style={{ marginTop: 16 }}>
            Symbols are heuristic candidates for now (closed shapes). Full AEC symbol training can
            come next.
          </p>
        </aside>
      </div>

      {(message || error) && (
        <div
          className="toast"
          onClick={() => {
            setMessage(null)
            setError(null)
          }}
        >
          {error || message}
        </div>
      )}
    </div>
  )
}
