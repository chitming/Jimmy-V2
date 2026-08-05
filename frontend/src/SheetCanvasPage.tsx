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
  snapshot: SheetElement
}

type PartFilter = 'all' | 'line' | 'circle' | 'text'

function sourceLabel(el: SheetElement) {
  if (el.source === 'stream_a') return 'Stream A'
  if (el.source === 'stream_b') return 'Stream B'
  if (el.source === 'original') return 'Reference'
  return el.type
}

function boundsFromLine(x1: number, y1: number, x2: number, y2: number) {
  const pad = 0.004
  const xmin = Math.min(x1, x2)
  const xmax = Math.max(x1, x2)
  const ymin = Math.min(y1, y2)
  const ymax = Math.max(y1, y2)
  return {
    x: Math.max(0, xmin - pad),
    y: Math.max(0, ymin - pad),
    w: Math.max(0.008, xmax - xmin + 2 * pad),
    h: Math.max(0.008, ymax - ymin + 2 * pad),
  }
}

export function SheetCanvasPage() {
  const { sheetId = '' } = useParams()
  const [sheet, setSheet] = useState<SheetCanvas | null>(null)
  const [elements, setElements] = useState<SheetElement[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<PartFilter>('all')
  const [showReference, setShowReference] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const paperRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<DragState | null>(null)

  async function load() {
    const data = await getSheetCanvas(sheetId)
    setSheet(data)
    setElements(data.elements)
    const first = data.elements.find((el) => el.type === 'line' || el.type === 'text' || el.type === 'circle')
    setSelectedId(first?.id ?? null)
  }

  useEffect(() => {
    if (!sheetId) return
    setError(null)
    load().catch((err) => setError(err.message))
  }, [sheetId])

  const paper = sheet?.paper
  const isLandscape = (paper?.orientation || 'landscape') === 'landscape'

  const visibleElements = useMemo(
    () =>
      elements.filter((el) => {
        if (el.hidden || el.type === 'meta') return false
        if (el.type === 'page' && !showReference) return false
        return true
      }),
    [elements, showReference],
  )

  const parts = useMemo(
    () => elements.filter((el) => el.type === 'line' || el.type === 'circle' || el.type === 'text' || el.type === 'label'),
    [elements],
  )

  const tableRows = useMemo(
    () => (filter === 'all' ? parts : parts.filter((el) => el.type === filter)),
    [parts, filter],
  )

  const counts = useMemo(
    () => ({
      line: parts.filter((el) => el.type === 'line').length,
      circle: parts.filter((el) => el.type === 'circle').length,
      text: parts.filter((el) => el.type === 'text' || el.type === 'label').length,
    }),
    [parts],
  )

  const selected = useMemo(
    () => elements.find((el) => el.id === selectedId) ?? null,
    [elements, selectedId],
  )

  function updateElement(id: string, patch: Partial<SheetElement>) {
    setElements((prev) => prev.map((el) => (el.id === id ? { ...el, ...patch } : el)))
  }

  function deleteElement(id: string) {
    setElements((prev) => prev.filter((el) => el.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  function onPointerDown(event: ReactPointerEvent, el: SheetElement) {
    if (el.locked || el.type === 'page') return
    event.preventDefault()
    event.stopPropagation()
    setSelectedId(el.id)
    const paperEl = paperRef.current
    if (!paperEl) return
    dragRef.current = {
      id: el.id,
      startX: event.clientX,
      startY: event.clientY,
      snapshot: { ...el },
    }
    ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: ReactPointerEvent) {
    const drag = dragRef.current
    const paperEl = paperRef.current
    if (!drag || !paperEl) return
    const rect = paperEl.getBoundingClientRect()
    const dx = (event.clientX - drag.startX) / rect.width
    const dy = (event.clientY - drag.startY) / rect.height
    const snap = drag.snapshot

    if (snap.type === 'line' && snap.x1 != null && snap.y1 != null && snap.x2 != null && snap.y2 != null) {
      const x1 = Math.min(1, Math.max(0, snap.x1 + dx))
      const y1 = Math.min(1, Math.max(0, snap.y1 + dy))
      const x2 = Math.min(1, Math.max(0, snap.x2 + dx))
      const y2 = Math.min(1, Math.max(0, snap.y2 + dy))
      updateElement(drag.id, { x1, y1, x2, y2, ...boundsFromLine(x1, y1, x2, y2) })
      return
    }

    if (snap.type === 'circle' && snap.cx != null && snap.cy != null && snap.r != null) {
      const cx = Math.min(1 - snap.r, Math.max(snap.r, snap.cx + dx))
      const cy = Math.min(1 - snap.r, Math.max(snap.r, snap.cy + dy))
      updateElement(drag.id, {
        cx,
        cy,
        x: cx - snap.r,
        y: cy - snap.r,
        w: 2 * snap.r,
        h: 2 * snap.r,
      })
      return
    }

    const nextX = Math.min(Math.max(0, snap.x + dx), 1 - snap.w)
    const nextY = Math.min(Math.max(0, snap.y + dy), 1 - snap.h)
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
      setMessage('Deconstruct worktop saved.')
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
      const saved = await saveSheetCanvas(sheet.id, { elements, orientation: next })
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
        <div className="empty">Loading deconstruct worktop…</div>
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
          <div className="brand-sub">Deconstruct worktop · A3 {paper.orientation}</div>
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
            {/* Reference + text/hit targets */}
            {visibleElements.map((el) => {
              if (el.type === 'line' || el.type === 'circle') {
                return (
                  <div
                    key={el.id}
                    className={`sheet-el sheet-el-hit${selectedId === el.id ? ' active' : ''}`}
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
                  />
                )
              }
              return (
                <div
                  key={el.id}
                  className={`sheet-el sheet-el-${el.type}${selectedId === el.id ? ' active' : ''}${el.locked ? ' locked' : ''}`}
                  style={{
                    left: `${el.x * 100}%`,
                    top: `${el.y * 100}%`,
                    width: `${el.w * 100}%`,
                    height: `${el.h * 100}%`,
                    opacity: el.type === 'page' ? el.opacity ?? 0.18 : undefined,
                  }}
                  onPointerDown={(event) => onPointerDown(event, el)}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (el.type !== 'page') setSelectedId(el.id)
                  }}
                >
                  {(el.type === 'page' || el.type === 'drawing') && el.image_url ? (
                    <img src={el.image_url} alt={el.label || 'Reference'} draggable={false} />
                  ) : null}
                  {el.type === 'text' || el.type === 'label' ? (
                    <textarea
                      className="sheet-el-edit"
                      value={el.text || ''}
                      onChange={(e) => updateElement(el.id, { text: e.target.value })}
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedId(el.id)
                      }}
                      spellCheck={false}
                    />
                  ) : null}
                </div>
              )
            })}

            {/* Vector overlay */}
            <svg className="sheet-vector-layer" viewBox="0 0 1 1" preserveAspectRatio="none">
              {elements
                .filter((el) => el.type === 'line' && el.x1 != null && el.y1 != null && el.x2 != null && el.y2 != null)
                .map((el) => (
                  <line
                    key={`svg-${el.id}`}
                    x1={el.x1}
                    y1={el.y1}
                    x2={el.x2}
                    y2={el.y2}
                    className={`sheet-svg-line${selectedId === el.id ? ' active' : ''}`}
                  />
                ))}
              {elements
                .filter((el) => el.type === 'circle' && el.cx != null && el.cy != null && el.r != null)
                .map((el) => (
                  <circle
                    key={`svg-${el.id}`}
                    cx={el.cx}
                    cy={el.cy}
                    r={el.r}
                    className={`sheet-svg-circle${selectedId === el.id ? ' active' : ''}`}
                  />
                ))}
            </svg>
          </div>

          <div className="sheet-flip-bar">
            <button className={`pill${showReference ? ' on' : ''}`} onClick={() => setShowReference((v) => !v)}>
              {showReference ? 'Hide reference' : 'Show reference'}
            </button>
            <button className="btn" disabled={busy} onClick={() => void onToggleOrientation()}>
              Flip to A3 {isLandscape ? 'portrait' : 'landscape'}
            </button>
          </div>
          <p className="help sheet-caption">
            {sheet.title} · {counts.line} lines · {counts.circle} circles · {counts.text} text ·{' '}
            {paper.width_mm}×{paper.height_mm} mm
          </p>
        </div>

        <section className="panel sheet-worktable-panel">
          <div className="section-head" style={{ marginTop: 0 }}>
            <div>
              <h2>Working space · deconstructed parts</h2>
              <p>Drawing broken into lines and text. Select, drag, edit, or delete parts.</p>
            </div>
          </div>

          <div className="pill-row" style={{ marginBottom: 12 }}>
            {(
              [
                ['all', `All · ${parts.length}`],
                ['line', `Lines · ${counts.line}`],
                ['circle', `Circles · ${counts.circle}`],
                ['text', `Text · ${counts.text}`],
              ] as Array<[PartFilter, string]>
            ).map(([key, label]) => (
              <button
                key={key}
                className={`pill${filter === key ? ' on' : ''}`}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>

          {selected && (selected.type === 'line' || selected.type === 'circle') && (
            <div className="field-list" style={{ marginBottom: 12 }}>
              <div className="field">
                <label>Selected</label>
                <div>
                  {selected.label} · {sourceLabel(selected)}
                </div>
              </div>
              {selected.type === 'line' && (
                <div className="field">
                  <label>Endpoints</label>
                  <div>
                    ({(selected.x1! * 100).toFixed(1)}%, {(selected.y1! * 100).toFixed(1)}%) → (
                    {(selected.x2! * 100).toFixed(1)}%, {(selected.y2! * 100).toFixed(1)}%)
                  </div>
                </div>
              )}
              {selected.type === 'circle' && (
                <div className="field">
                  <label>Circle</label>
                  <div>
                    center {(selected.cx! * 100).toFixed(1)}%, {(selected.cy! * 100).toFixed(1)}% · r{' '}
                    {(selected.r! * 100).toFixed(1)}%
                  </div>
                </div>
              )}
              <button className="btn" onClick={() => deleteElement(selected.id)}>
                Delete selected
              </button>
            </div>
          )}

          <div className="table-wrap">
            <table className="data-table sheet-worktable">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Label / Text</th>
                  <th>Geometry</th>
                  <th></th>
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
                      {el.type === 'text' || el.type === 'label' ? (
                        <input
                          className="sheet-input"
                          value={el.text || ''}
                          onChange={(e) => updateElement(el.id, { text: e.target.value })}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <input
                          className="sheet-input"
                          value={el.label || ''}
                          onChange={(e) => updateElement(el.id, { label: e.target.value })}
                          onClick={(e) => e.stopPropagation()}
                        />
                      )}
                    </td>
                    <td className="sheet-pos-cell">
                      {el.type === 'line'
                        ? `${(el.x1! * 100).toFixed(0)},${(el.y1! * 100).toFixed(0)}→${(el.x2! * 100).toFixed(0)},${(el.y2! * 100).toFixed(0)}`
                        : el.type === 'circle'
                          ? `c ${(el.cx! * 100).toFixed(0)},${(el.cy! * 100).toFixed(0)} r${(el.r! * 100).toFixed(0)}`
                          : `${(el.x * 100).toFixed(0)}%,${(el.y * 100).toFixed(0)}%`}
                    </td>
                    <td>
                      <button
                        className="btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteElement(el.id)
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {tableRows.length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      No deconstructed parts yet. Run Stream B, then Compose A3 sheet canvas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
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
