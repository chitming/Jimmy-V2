import { Navigate, Route, Routes } from 'react-router-dom'
import { HomePage } from './HomePage'
import { LibraryPage } from './LibraryPage'
import { SheetCanvasPage } from './SheetCanvasPage'
import { TeachPage } from './TeachPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/library" element={<LibraryPage />} />
      <Route path="/teach/:pageId" element={<TeachPage />} />
      <Route path="/sheet-canvas/:sheetId" element={<SheetCanvasPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
