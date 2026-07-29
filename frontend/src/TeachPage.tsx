import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  extractPage,
  getPage,
  saveAnnotation,
  type Box,
  type PageDetail,
} from './api'
import { Annotator } from './Annotator'

type Tool = 'information_block' | 'drawing_canvas'

const FIELD_LABELS: Record<string, string> = {
  company: 'Company',
  title: 'Title',
  drawing_number: 'Drawing number',
  revision: 'Revision',
  scale: 'Scale',
  date: 'Date',
}

export function TeachPage() {
  const { pageId = '' } = useParams()
  const [page, setPage] = useState<PageDetail | null>(null)
  const [tool, setTool] = useState<Tool>('information_block')
  const [info, setInfo] = useState<Box | null>(null)
  const [canvas, setCanvas] = useState<Box | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!pageId) return
    setError(null)
    getPage(pageId)
      .then((data) => {
        setPage(data)
        setInfo(data.annotation?.information_block ?? null)
        setCanvas(data.annotation?.drawing_canvas ?? null)
      })
      .catch((err) => setError(err.message))
  }, [pageId])

  const canSave = Boolean(info && canvas)
  const suggestion = page?.suggestion ?? null

  const confidenceLabel = useMemo(() => {
    if (!suggestion) return null
    return `${Math.round(suggestion.confidence * 100)}% from ${suggestion.examples_used} prior sheet${
      suggestion.examples_used === 1 ? '' : 's'
    }`
  }, [suggestion])

  async function acceptSuggestion() {
    if (!suggestion) return
    setInfo(suggestion.information_block)
    setCanvas(suggestion.drawing_canvas)
    setMessage('Accepted machine suggestion. Save to teach it.')
  }

  async function onSave() {
    if (!pageId || !info || !canvas) return
    setBusy(true)
    setError(null)
    try {
      await saveAnnotation(pageId, info, canvas)
      const refreshed = await getPage(pageId)
      setPage(refreshed)
      setMessage('Saved. JPG segments stored in Info Block and Drawing folders.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  async function onExtract() {
    if (!pageId) return
    if (!info || !canvas) {
      setError('Teach both regions and save before extracting.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await saveAnnotation(pageId, info, canvas)
      await extractPage(pageId)
      const refreshed = await getPage(pageId)
      setPage(refreshed)
      setInfo(refreshed.annotation?.information_block ?? info)
      setCanvas(refreshed.annotation?.drawing_canvas ?? canvas)
      setMessage('Information block extracted.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extract failed')
    } finally {
      setBusy(false)
    }
  }

  if (error && !page) {
    return (
      <div className="app-shell">
        <div className="empty">{error}</div>
        <p>
          <Link to="/">Back home</Link>
        </p>
      </div>
    )
  }

  if (!page) {
    return (
      <div className="app-shell">
        <div className="empty">Loading drawing…</div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-mark">
            SHEET<span>SENSE</span>
          </Link>
          <div className="brand-sub">
            {page.filename} · page {page.page_index + 1}
          </div>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" to="/">
            Library
          </Link>
          <Link className="btn btn-ghost" to="/library">
            Segments
          </Link>
          <button className="btn" disabled={!canSave || busy} onClick={() => void onSave()}>
            Save teaching
          </button>
          <button className="btn btn-primary" disabled={!canSave || busy} onClick={() => void onExtract()}>
            Extract info block
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="panel">
          <h2>Teach two regions</h2>
          <p className="help">
            Select a tool, then drag on the drawing. Start with the information block, then mark the
            drawing canvas.
          </p>
          <div className="tool-list">
            <button
              className={`tool${tool === 'information_block' ? ' active-info' : ''}`}
              onClick={() => setTool('information_block')}
            >
              <strong>1. Information block</strong>
              <span>Company, drawing number, revision, scale</span>
            </button>
            <button
              className={`tool${tool === 'drawing_canvas' ? ' active-canvas' : ''}`}
              onClick={() => setTool('drawing_canvas')}
            >
              <strong>2. Drawing canvas</strong>
              <span>Main geometry / views area</span>
            </button>
          </div>

          {suggestion && (
            <div style={{ marginTop: 8 }}>
              <p className="help">Machine suggestion ready · {confidenceLabel}</p>
              <button className="btn" style={{ width: '100%' }} onClick={() => void acceptSuggestion()}>
                Accept suggestion
              </button>
            </div>
          )}

          {!suggestion && (
            <p className="help" style={{ marginTop: 12 }}>
              No suggestion yet. Teach the first sheet and the next similar one will get a proposal.
            </p>
          )}
        </aside>

        <Annotator
          imageUrl={page.image_url}
          informationBlock={info}
          drawingCanvas={canvas}
          suggestion={suggestion}
          activeTool={tool}
          onChange={({ information_block, drawing_canvas }) => {
            setInfo(information_block)
            setCanvas(drawing_canvas)
            if (information_block && !drawing_canvas) setTool('drawing_canvas')
          }}
        />

        <aside className="panel">
          <h2>Extracted fields</h2>
          {page.annotation?.segments && (
            <div className="field-list" style={{ marginBottom: 14 }}>
              {page.annotation.segments.info_block && (
                <div className="field">
                  <label>Info Block JPG</label>
                  <div>{page.annotation.segments.info_block.filename}</div>
                </div>
              )}
              {page.annotation.segments.drawing && (
                <div className="field">
                  <label>Drawing JPG</label>
                  <div>{page.annotation.segments.drawing.filename}</div>
                </div>
              )}
            </div>
          )}
          {!page.extraction && (
            <p className="help">Save both regions, then extract. Vector PDFs use native text when possible.</p>
          )}
          {page.extraction && (
            <>
              <div className="field-list">
                {Object.entries(FIELD_LABELS).map(([key, label]) => (
                  <div className="field" key={key}>
                    <label>{label}</label>
                    <div>{page.extraction?.fields?.[key] || '—'}</div>
                  </div>
                ))}
              </div>
              <div className="raw-text">
                <div style={{ marginBottom: 6 }}>Method: {page.extraction.method}</div>
                {page.extraction.raw_text || 'No text found in information block.'}
              </div>
              {page.extraction.crop_url && (
                <img
                  src={page.extraction.crop_url}
                  alt="Information block crop"
                  style={{ width: '100%', marginTop: 12, borderRadius: 8, border: '1px solid var(--line)' }}
                />
              )}
            </>
          )}
        </aside>
      </div>

      {(message || error) && (
        <div className="toast" onClick={() => { setMessage(null); setError(null) }}>
          {error || message}
        </div>
      )}
    </div>
  )
}
