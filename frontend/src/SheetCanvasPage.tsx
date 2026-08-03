import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  getSheetCanvas,
  saveSheetCanvas,
  type SheetCanvas,
  type SheetElement,
} from './api'

type DragState = {
  id: string
  startX: number
  startY: number
  origX: number
  origY: number
}

export function SheetCanvasPage() {
  const { sheetId = '' } = useParams()
  const [sheet, setSheet] = useState<SheetCanvas | null>(null)
  const [elements, setElements] = useState<SheetElement[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const paperRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<DragState | null>(null)

  async function load() {
    const data = await getSheetCanvas(sheetId)
    setSheet(data)
    setElements(data.elements)
    setSelectedId(data.elements[0]?.id ?? null)
  }

  useEffect(() => {
    if (!sheetId) return
    setError(null)
    load().catch((err) => setError(err.message))
  }, [sheetId])

  const selected = useMemo(
    () => elements.find((el) => el.id === selectedId) ?? null,
    [elements, selectedId],
  )

  const paper = sheet?.paper
  const isLandscape = (paper?.orientation || 'landscape') === 'landscape'

  function updateElement(id: string, patch: Partial<SheetElement>) {
    setElements((prev) => prev.map((el) => (el.id === id ? { ...el, ...patch } : el)))
  }

  function onPointerDown(event: ReactPointerEvent, el: SheetElement) {
    if (el.locked) return
    event.preventDefault()
    event.stopPropagation()
    setSelectedId(el.id)
    const paperEl = paperRef.current
    if (!paperEl) return
    dragRef.current = {
      id: el.id,
      startX: event.clientX,
      startY: event.clientY,
      origX: el.x,
      origY: el.y,
    }
    ;(event.target as HTMLElement).setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: ReactPointerEvent) {
    const drag = dragRef.current
    const paperEl = paperRef.current
    if (!drag || !paperEl) return
    const rect = paperEl.getBoundingClientRect()
    const dx = (event.clientX - drag.startX) / rect.width
    const dy = (event.clientY - drag.startY) / rect.height
    const el = elements.find((item) => item.id === drag.id)
    if (!el) return
    const nextX = Math.min(Math.max(0, drag.origX + dx), 1 - el.w)
    const nextY = Math.min(Math.max(0, drag.origY + dy), 1 - el.h)
    updateElement(drag.id, { x: nextX, y: nextY })
  }

  function onPointerUp() {
    dragRef.current = null
  }

  async function onSave() {
    if (!sheet) return
    setBusy(true)
    setError(null)
    try {
      const saved = await saveSheetCanvas(sheet.id, { elements, status: 'draft' })
      setSheet(saved)
      setElements(saved.elements)
      setMessage('Sheet canvas saved.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  async function onToggleOrientation() {
    if (!sheet) return
    setBusy(true)
    setError(null)
    try {
      const next = isLandscape ? 'portrait' : 'landscape'
      const saved = await saveSheetCanvas(sheet.id, {
        elements,
        orientation: next,
      })
      setSheet(saved)
      setElements(saved.elements)
      setMessage(`Paper set to A4 ${next}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Orientation change failed')
    } finally {
      setBusy(false)
    }
  }

  if (error && !sheet) {
    return (
      <div className="app-shell">
        <div className="empty">{error}</div>
        <div className="nav-actions" style={{ marginTop: 16 }}>
          <Link className="btn" to="/library">
            Back to library
          </Link>
        </div>
      </div>
    )
  }

  if (!sheet || !paper) {
    return (
      <div className="app-shell">
        <div className="empty">Loading sheet canvas…</div>
      </div>
    )
  }

  return (
    <div className="app-shell sheet-shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-mark" aria-label="Home">
            T<span>DR</span>
          </Link>
          <div className="brand-sub">Sheet canvas · A4 {paper.orientation}</div>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" to="/library">
            Open Segment library
          </Link>
          <button className="btn" disabled={busy} onClick={() => void onToggleOrientation()}>
            Flip to A4 {isLandscape ? 'portrait' : 'landscape'}
          </button>
          <button className="btn btn-primary" disabled={busy} onClick={() => void onSave()}>
            Save sheet
          </button>
        </div>
      </header>

      <div className="sheet-workspace">
        <aside className="panel sheet-tools">
          <h2>Working space</h2>
          <p className="help">
            Stream A (Info Block) and Stream B (Drawing) are placed on one A4 sheet
            (horizontal by default). Drag items to move. Edit text on the right.
            More tools will be added later.
          </p>
          <div className="status-banner">
            {paper.width_mm} × {paper.height_mm} mm · {elements.length} item
            {elements.length === 1 ? '' : 's'}
          </div>
          <div className="field-list" style={{ marginTop: 12 }}>
            {elements.map((el) => (
              <button
                key={el.id}
                className={`ocr-item${selectedId === el.id ? ' active' : ''}`}
                onClick={() => setSelectedId(el.id)}
              >
                <strong>{el.label || el.type}</strong>
                <span>{el.source === 'stream_a' ? 'Stream A' : el.source === 'stream_b' ? 'Stream B' : el.type}</span>
              </button>
            ))}
          </div>
          <div className="tool-placeholder">
            <h3>Tools</h3>
            <p className="help">Coming next: snap, align, measure, export PDF.</p>
          </div>
        </aside>

        <div className="sheet-stage-wrap">
          <div
            ref={paperRef}
            className={`sheet-paper${isLandscape ? ' landscape' : ' portrait'}`}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={onPointerUp}
            onClick={() => setSelectedId(null)}
          >
            <div className="sheet-margin-guide" />
            {elements.map((el) => (
              <div
                key={el.id}
                className={`sheet-el sheet-el-${el.type}${selectedId === el.id ? ' active' : ''}`}
                style={{
                  left: `${el.x * 100}%`,
                  top: `${el.y * 100}%`,
                  width: `${el.w * 100}%`,
                  height: `${el.h * 100}%`,
                }}
                onPointerDown={(event) => onPointerDown(event, el)}
                onClick={(event) => {
                  event.stopPropagation()
                  setSelectedId(el.id)
                }}
              >
                {el.type === 'drawing' && el.image_url ? (
                  <img src={el.image_url} alt={el.label || 'Drawing'} draggable={false} />
                ) : null}
                {(el.type === 'text' || el.type === 'label') && (
                  <div className="sheet-el-text">{el.text || ''}</div>
                )}
              </div>
            ))}
          </div>
          <p className="help sheet-caption">{sheet.title}</p>
        </div>

        <aside className="panel">
          <h2>Edit selected</h2>
          {!selected && <p className="help">Select an item on the sheet to edit.</p>}
          {selected && (
            <>
              <label className="help" htmlFor="sheet-el-label">
                Label
              </label>
              <input
                id="sheet-el-label"
                className="sheet-input"
                value={selected.label || ''}
                onChange={(e) => updateElement(selected.id, { label: e.target.value })}
              />
              {(selected.type === 'text' || selected.type === 'label') && (
                <>
                  <label className="help" htmlFor="sheet-el-text" style={{ marginTop: 12 }}>
                    Text
                  </label>
                  <textarea
                    id="sheet-el-text"
                    className="ocr-edit"
                    value={selected.text || ''}
                    onChange={(e) => updateElement(selected.id, { text: e.target.value })}
                  />
                </>
              )}
              {selected.type === 'drawing' && selected.dxf_url && (
                <p className="help" style={{ marginTop: 12 }}>
                  Linked DXF available from Stream B.
                </p>
              )}
              <div className="field-list" style={{ marginTop: 12 }}>
                <div className="field">
                  <label>Position</label>
                  <div>
                    x {(selected.x * 100).toFixed(1)}% · y {(selected.y * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="field">
                  <label>Size</label>
                  <div>
                    w {(selected.w * 100).toFixed(1)}% · h {(selected.h * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </>
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
