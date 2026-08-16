import { useEffect, useRef, useState } from 'react'
import type { Box } from './api'

type ActiveTool = 'information_block' | 'drawing_canvas'

type Props = {
  imageUrl: string
  informationBlock: Box | null
  drawingCanvas: Box | null
  accepted?: boolean
  activeTool: ActiveTool
  onChange: (next: { information_block: Box | null; drawing_canvas: Box | null }) => void
}

function normBox(a: { x: number; y: number }, b: { x: number; y: number }): Box {
  const x = Math.min(a.x, b.x)
  const y = Math.min(a.y, b.y)
  const w = Math.abs(a.x - b.x)
  const h = Math.abs(a.y - b.y)
  return {
    x: Math.max(0, Math.min(x, 1)),
    y: Math.max(0, Math.min(y, 1)),
    w: Math.max(0.01, Math.min(w, 1 - x)),
    h: Math.max(0.01, Math.min(h, 1 - y)),
  }
}

export function Annotator({
  imageUrl,
  informationBlock,
  drawingCanvas,
  accepted = false,
  activeTool,
  onChange,
}: Props) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [draft, setDraft] = useState<Box | null>(null)
  const dragStart = useRef<{ x: number; y: number } | null>(null)

  useEffect(() => {
    setDraft(null)
    dragStart.current = null
  }, [imageUrl, activeTool])

  function toNorm(clientX: number, clientY: number) {
    const img = imgRef.current
    if (!img) return { x: 0, y: 0 }
    const rect = img.getBoundingClientRect()
    return {
      x: Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (clientY - rect.top) / rect.height)),
    }
  }

  function onPointerDown(e: React.PointerEvent) {
    const start = toNorm(e.clientX, e.clientY)
    dragStart.current = start
    setDraft({ x: start.x, y: start.y, w: 0.01, h: 0.01 })
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!dragStart.current) return
    const current = toNorm(e.clientX, e.clientY)
    setDraft(normBox(dragStart.current, current))
  }

  function onPointerUp(e: React.PointerEvent) {
    if (!dragStart.current) return
    const current = toNorm(e.clientX, e.clientY)
    const box = normBox(dragStart.current, current)
    dragStart.current = null
    setDraft(null)
    if (box.w < 0.015 || box.h < 0.015) return
    if (activeTool === 'information_block') {
      onChange({ information_block: box, drawing_canvas: drawingCanvas })
    } else {
      onChange({ information_block: informationBlock, drawing_canvas: box })
    }
  }

  const boxes: Array<{ key: string; box: Box; kind: 'info' | 'canvas'; label: string; pending?: boolean }> =
    []
  if (informationBlock) {
    boxes.push({
      key: 'info',
      box: informationBlock,
      kind: 'info',
      label: accepted ? 'Info block · accepted' : 'Info block · machine',
      pending: !accepted,
    })
  }
  if (drawingCanvas) {
    boxes.push({
      key: 'canvas',
      box: drawingCanvas,
      kind: 'canvas',
      label: accepted ? 'Drawing · accepted' : 'Drawing · machine',
      pending: !accepted,
    })
  }
  if (draft) {
    boxes.push({
      key: 'draft',
      box: draft,
      kind: activeTool === 'information_block' ? 'info' : 'canvas',
      label: 'Correcting…',
    })
  }

  return (
    <div className="stage-wrap">
      <div className="stage">
        <img ref={imgRef} src={imageUrl} alt="Technical drawing page" draggable={false} />
        <div
          className="overlay"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          {boxes.map((item) => (
            <div
              key={item.key}
              className={`box ${item.kind}${item.pending ? ' pending' : ' accepted-box'}`}
              style={{
                left: `${item.box.x * 100}%`,
                top: `${item.box.y * 100}%`,
                width: `${item.box.w * 100}%`,
                height: `${item.box.h * 100}%`,
              }}
            >
              <div className="box-label">{item.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
