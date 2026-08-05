export type Box = {
  x: number
  y: number
  w: number
  h: number
}

export type PageSummary = {
  id: string
  page_index: number
  width: number
  height: number
  image_url: string
  status: string
  has_annotation?: boolean
  has_extraction?: boolean
}

export type Drawing = {
  id: string
  filename: string
  source_type: string
  page_count: number
  created_at: string
  pages: PageSummary[]
}

export type Suggestion = {
  information_block: Box
  drawing_canvas: Box
  confidence: number
  examples_used: number
  labeled_total: number
  method: string
}

export type Stats = {
  drawings: number
  pages: number
  labeled: number
  extracted: number
  info_block_segments: number
  drawing_segments: number
}

export type LibraryItem = {
  id: string
  page_id: string
  drawing_id: string
  kind: 'info_block' | 'drawing'
  folder: string
  filename: string
  source_filename: string
  page_index: number
  created_at: string
  exists: boolean
  url: string
}

export type PageDetail = {
  id: string
  drawing_id: string
  filename: string
  source_type: string
  page_index: number
  width: number
  height: number
  image_url: string
  status: string
  annotation: {
    information_block: Box
    drawing_canvas: Box
    updated_at: string
    segments?: Record<string, { folder: string; filename: string; url: string }>
  } | null
  extraction: {
    raw_text: string
    fields: Record<string, string | null>
    method: string
    crop_url: string
    created_at: string
  } | null
  suggestion: Suggestion | null
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export function getStats() {
  return request<Stats>('/api/stats')
}

export function listDrawings() {
  return request<{ drawings: Drawing[] }>('/api/drawings')
}

export function getPage(pageId: string) {
  return request<PageDetail>(`/api/pages/${pageId}`)
}

export async function uploadDrawing(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<{
    id: string
    filename: string
    source_type: string
    page_count: number
    pages: PageSummary[]
  }>('/api/drawings/upload', { method: 'POST', body })
}

export function saveAnnotation(pageId: string, information_block: Box, drawing_canvas: Box) {
  return request(`/api/pages/${pageId}/annotation`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ information_block, drawing_canvas }),
  })
}

export function extractPage(pageId: string) {
  return request<PageDetail['extraction'] & { id: string; page_id: string; library_folder?: string }>(
    `/api/pages/${pageId}/extract`,
    { method: 'POST' },
  )
}

export function getLibrary(kind?: 'info_block' | 'drawing') {
  const query = kind ? `?kind=${kind}` : ''
  return request<{
    folders: string[]
    counts: { info_block: number; drawing: number }
    items: LibraryItem[]
  }>(`/api/library${query}`)
}

export type InfoBlockRow = {
  id: string
  segment_id: string
  page_id: string
  source_filename: string
  segment_filename: string
  page_index: number
  raw_text: string
  fields: Record<string, string>
  field_count: number
  method: string
  created_at: string
  updated_at: string
  image_url: string
}

export function getInfoBlockRows() {
  return request<{
    count: number
    max_fields: number
    field_headers: string[]
    rows: InfoBlockRow[]
  }>('/api/info-blocks')
}

export function runInfoBlockOcr() {
  return request<{
    processed: number
    errors: Array<{ segment_id: string; error: string }>
    rows: Array<{
      id: string
      source_filename: string
      field_count: number
      fields: Record<string, string>
    }>
    all_rows: InfoBlockRow[]
  }>('/api/info-blocks/ocr', { method: 'POST' })
}

export function downloadInfoBlockExcel() {
  return fetch('/api/info-blocks/export.xlsx').then(async (res) => {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const data = await res.json()
        detail = data.detail || detail
      } catch {
        /* ignore */
      }
      throw new Error(typeof detail === 'string' ? detail : 'Excel export failed')
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'tdr_info_blocks.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  })
}

export type DrawingOcrRun = {
  id: string
  segment_id: string
  page_id: string
  source_filename: string
  segment_filename: string
  page_index: number
  image_width: number
  image_height: number
  engine: string
  items: Array<{
    id: string
    text: string
    score: number
    box: Box
    pixel_box?: number[]
    edited?: boolean
  }>
  item_count: number
  status: string
  created_at: string
  updated_at: string
  image_url: string
  preview_url?: string | null
  cleaned_url?: string | null
  dxf_url?: string | null
  loop?: string[]
  vectors?: {
    lines: Array<Record<string, number | string>>
    circles: Array<Record<string, number | string>>
    arcs: Array<Record<string, number | string>>
    symbols: Array<Record<string, number | string>>
  }
  stages?: Array<{ id: string; label: string; ok: boolean; detail?: Record<string, unknown> }>
  counts?: {
    lines?: number
    circles?: number
    arcs?: number
    symbols?: number
    texts?: number
  }
}

export function listDrawingOcrRuns() {
  return request<{ engine: string; count: number; runs: DrawingOcrRun[] }>('/api/drawings-ocr')
}

export function runDrawingOcr(pageId?: string) {
  const query = pageId ? `?page_id=${encodeURIComponent(pageId)}` : ''
  return request<{
    engine: string
    pipeline?: string[]
    processed: number
    errors: Array<{ segment_id: string; error: string }>
    runs: Array<{
      id: string
      page_id: string
      item_count: number
      dxf_url?: string
      preview_url?: string
    }>
    all_runs: DrawingOcrRun[]
  }>(`/api/drawings-ocr/run${query}`, { method: 'POST' })
}

export function downloadDrawingDxf(pageId: string) {
  return fetch(`/api/drawings-ocr/${pageId}/export.dxf`).then(async (res) => {
    if (!res.ok) {
      let detail = res.statusText
      try {
        const data = await res.json()
        detail = data.detail || detail
      } catch {
        /* ignore */
      }
      throw new Error(typeof detail === 'string' ? detail : 'DXF export failed')
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${pageId}.dxf`
    a.click()
    URL.revokeObjectURL(url)
  })
}

export type SheetElement = {
  id: string
  type: 'drawing' | 'text' | 'label' | 'page' | 'meta' | 'line' | 'circle' | string
  source?: string
  page_id?: string
  label?: string
  field_key?: string
  text?: string
  image_url?: string | null
  dxf_url?: string | null
  x: number
  y: number
  w: number
  h: number
  x1?: number
  y1?: number
  x2?: number
  y2?: number
  cx?: number
  cy?: number
  r?: number
  length?: number
  locked?: boolean
  editable?: boolean
  hidden?: boolean
  opacity?: number
}

export type SheetCanvas = {
  id: string
  page_id: string
  title: string
  paper: {
    size: string
    orientation: 'landscape' | 'portrait' | string
    width_mm: number
    height_mm: number
    unit?: string
  }
  elements: SheetElement[]
  status: string
  created_at: string
  updated_at: string
  edit_url: string
}

export function listSheetCanvases() {
  return request<{
    count: number
    paper_default: SheetCanvas['paper']
    sheets: SheetCanvas[]
  }>('/api/sheet-canvas')
}

export function composeSheetCanvas(pageId?: string, orientation = 'landscape') {
  const params = new URLSearchParams()
  if (pageId) params.set('page_id', pageId)
  params.set('orientation', orientation)
  return request<{
    paper_default: SheetCanvas['paper']
    processed: number
    sheets: SheetCanvas[]
    all_sheets: SheetCanvas[]
  }>(`/api/sheet-canvas/compose?${params.toString()}`, { method: 'POST' })
}

export function getSheetCanvas(sheetId: string) {
  return request<SheetCanvas>(`/api/sheet-canvas/${sheetId}`)
}

export function saveSheetCanvas(
  sheetId: string,
  payload: {
    elements?: SheetElement[]
    title?: string
    orientation?: string
    status?: string
  },
) {
  return request<SheetCanvas>(`/api/sheet-canvas/${sheetId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
