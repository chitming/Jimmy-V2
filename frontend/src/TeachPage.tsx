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

function sameBox(a: Box | null, b: Box | null) {
  if (!a || !b) return false
  return (
    Math.abs(a.x - b.x) < 1e-6 &&
    Math.abs(a.y - b.y) < 1e-6 &&
    Math.abs(a.w - b.w) < 1e-6 &&
    Math.abs(a.h - b.h) < 1e-6
  )
}

export function TeachPage() {
  const { pageId = '' } = useParams()
  const [page, setPage] = useState<PageDetail | null>(null)
  const [tool, setTool] = useState<Tool>('information_block')
  const [info, setInfo] = useState<Box | null>(null)
  const [canvas, setCanvas] = useState<Box | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!pageId) return
    setError(null)
    setMessage(null)
    getPage(pageId)
      .then((data) => {
        setPage(data)
        // Machine goes first: use saved agreement if present, otherwise machine proposal.
        if (data.annotation) {
          setInfo(data.annotation.information_block)
          setCanvas(data.annotation.drawing_canvas)
          setAccepted(true)
        } else if (data.suggestion) {
          setInfo(data.suggestion.information_block)
          setCanvas(data.suggestion.drawing_canvas)
          setAccepted(false)
        } else {
          setInfo(null)
          setCanvas(null)
          setAccepted(false)
        }
      })
      .catch((err) => setError(err.message))
  }, [pageId])

  const suggestion = page?.suggestion ?? null
  const canAccept = Boolean(info && canvas)

  const statusLabel = useMemo(() => {
    if (accepted) return 'Accepted — machine and you agree on this sheet'
    if (!suggestion) return 'Waiting for machine proposal'
    if (suggestion.method === 'aec_default') {
      return 'Machine selected first (AEC default). Correct if needed, then Accept.'
    }
    return `Machine selected first · ${Math.round(suggestion.confidence * 100)}% from ${
      suggestion.examples_used
    } prior sheet${suggestion.examples_used === 1 ? '' : 's'}`
  }, [accepted, suggestion])

  function markEdited(nextInfo: Box | null, nextCanvas: Box | null) {
    setInfo(nextInfo)
    setCanvas(nextCanvas)
    if (!page?.annotation) {
      setAccepted(false)
      return
    }
    const unchanged =
      sameBox(nextInfo, page.annotation.information_block) &&
      sameBox(nextCanvas, page.annotation.drawing_canvas)
    setAccepted(unchanged)
  }

  async function onAccept() {
    if (!pageId || !info || !canvas) return
    setBusy(true)
    setError(null)
    try {
      await saveAnnotation(pageId, info, canvas)
      const refreshed = await getPage(pageId)
      setPage(refreshed)
      setInfo(refreshed.annotation?.information_block ?? info)
      setCanvas(refreshed.annotation?.drawing_canvas ?? canvas)
      setAccepted(true)
      setMessage('Accepted. This agreement is now a learning example, and JPGs were saved to the library.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Accept failed')
    } finally {
      setBusy(false)
    }
  }

  async function onExtract() {
    if (!pageId || !info || !canvas) {
      setError('Accept the two regions first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      if (!accepted) {
        await saveAnnotation(pageId, info, canvas)
        setAccepted(true)
      }
      await extractPage(pageId)
      const refreshed = await getPage(pageId)
      setPage(refreshed)
      setInfo(refreshed.annotation?.information_block ?? info)
      setCanvas(refreshed.annotation?.drawing_canvas ?? canvas)
      setMessage('Info Block text extracted. Use Segment library for Field1… Excel export.')
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
          <Link to="/" className="brand-mark" aria-label="Home">
            T<span>DR</span>
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
            Open Segment library
          </Link>
          <button className="btn btn-primary" disabled={!canAccept || busy || accepted} onClick={() => void onAccept()}>
            {accepted ? 'Accepted' : 'Accept'}
          </button>
          <button className="btn" disabled={!canAccept || busy} onClick={() => void onExtract()}>
            Extract info block
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="panel">
          <h2>Machine selects first</h2>
          <p className="help">
            The machine marks Info Block and Drawing. Change a box only if it is wrong. Click{' '}
            <strong>Accept</strong> when you agree — that finalizes learning for this sheet.
          </p>

          <div className={`status-banner${accepted ? ' ok' : ''}`}>{statusLabel}</div>

          <div className="tool-list">
            <button
              className={`tool${tool === 'information_block' ? ' active-info' : ''}`}
              onClick={() => setTool('information_block')}
            >
              <strong>1. Information block</strong>
              <span>Correct only if the machine box is wrong</span>
            </button>
            <button
              className={`tool${tool === 'drawing_canvas' ? ' active-canvas' : ''}`}
              onClick={() => setTool('drawing_canvas')}
            >
              <strong>2. Drawing canvas</strong>
              <span>Correct only if the machine box is wrong</span>
            </button>
          </div>

          <button
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 8 }}
            disabled={!canAccept || busy || accepted}
            onClick={() => void onAccept()}
          >
            {accepted ? 'Accepted — learning saved' : 'Accept'}
          </button>

          {!accepted && (
            <p className="help" style={{ marginTop: 12 }}>
              Accept = you and the machine agree. TDR learns from that agreement and saves JPG
              segments to the library.
            </p>
          )}
          {accepted && (
            <p className="help" style={{ marginTop: 12 }}>
              To change the agreement, redraw a box, then Accept again.
            </p>
          )}
        </aside>

        <Annotator
          imageUrl={page.image_url}
          informationBlock={info}
          drawingCanvas={canvas}
          accepted={accepted}
          activeTool={tool}
          onChange={({ information_block, drawing_canvas }) => {
            markEdited(information_block, drawing_canvas)
            if (information_block && !drawing_canvas) setTool('drawing_canvas')
          }}
        />

        <aside className="panel">
          <h2>Agreement result</h2>
          {page.annotation?.segments ? (
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
          ) : (
            <p className="help">After Accept, JPG crops appear in the Info Block and Drawing folders.</p>
          )}

          {page.extraction ? (
            <>
              <div className="raw-text">
                <div style={{ marginBottom: 6 }}>Extract preview · {page.extraction.method}</div>
                {page.extraction.raw_text || 'No text found in information block.'}
              </div>
              <p className="help" style={{ marginTop: 12 }}>
                For Field1… Excel export, open Segment library → OCR Info Blocks.
              </p>
            </>
          ) : (
            <p className="help">Optional: Extract info block text after Accept.</p>
          )}
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
