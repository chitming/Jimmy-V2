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
