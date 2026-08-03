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

function sourceLabel(el: SheetElement) {
  if (el.source === 'stream_a') return 'Stream A'
  if (el.source === 'stream_b') return 'Stream B'
  return el.type
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
  const tableRows = useMemo(
    () => elements.filter((el) => el.type !== 'drawing'),
    [elements],
  )
  const drawingEl = useMemo(
    () => elements.find((el) => el.type === 'drawing') ?? null,
    [elements],
  )

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
      setMessage(`Paper set to A3 ${next}.`)
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
          <div className="brand-sub">Sheet canvas · A3 {paper.orientation}</div>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" to="/library">
            Open Segment library
          </Link>
          <button className="btn btn-primary" disabled={busy} onClick={() => void onSave()}>
            Save sheet
          </button>
        </div>
      </header>

      <div className="sheet-workspace sheet-workspace-stacked">
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
                  <div className="sheet-el-text">
                    {el.type === 'text' && el.label ? (
                      <strong className="sheet-el-fieldkey">{el.label}</strong>
                    ) : null}
                    {el.text || ''}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="sheet-flip-bar">
            <button className="btn" disabled={busy} onClick={() => void onToggleOrientation()}>
              Flip to A3 {isLandscape ? 'portrait' : 'landscape'}
            </button>
          </div>
          <p className="help sheet-caption">
            {sheet.title} · {paper.width_mm} × {paper.height_mm} mm
            {drawingEl?.dxf_url ? ' · Stream B DXF linked' : ''}
          </p>
        </div>

        <section className="panel sheet-worktable-panel">
          <div className="section-head" style={{ marginTop: 0 }}>
            <div>
              <h2>Working space</h2>
              <p>
                Table under the drawing canvas. Edit Stream A fields here; more tools later.
              </p>
            </div>
          </div>
          <div className="table-wrap">
            <table className="data-table sheet-worktable">
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Source</th>
                  <th>Label</th>
                  <th>Text</th>
                  <th>Position</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((el) => (
                  <tr
                    key={el.id}
                    className={selectedId === el.id ? 'active-row' : undefined}
                    onClick={() => setSelectedId(el.id)}
                  >
                    <td>{el.type}</td>
                    <td>{sourceLabel(el)}</td>
                    <td>
                      <input
                        className="sheet-input"
                        value={el.label || ''}
                        onChange={(e) => updateElement(el.id, { label: e.target.value })}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                    <td>
                      <input
                        className="sheet-input"
                        value={el.text || ''}
                        onChange={(e) => updateElement(el.id, { text: e.target.value })}
                        onClick={(e) => e.stopPropagation()}
                        disabled={el.type === 'drawing'}
                      />
                    </td>
                    <td className="sheet-pos-cell">
                      {(el.x * 100).toFixed(0)}%,{(el.y * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
                {tableRows.length === 0 && (
                  <tr>
                    <td colSpan={5}>No working-space rows yet. Compose Stream A + B first.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {selected?.type === 'drawing' && (
            <p className="help" style={{ marginTop: 10 }}>
              Drawing selected on canvas. Stream B preview sits above this table.
            </p>
          )}
          <p className="help" style={{ marginTop: 10 }}>
            Tools coming next: snap, align, measure, export PDF.
          </p>
        </section>
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
