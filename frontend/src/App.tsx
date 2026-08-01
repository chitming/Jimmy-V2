import { Navigate, Route, Routes } from 'react-router-dom'
import { DrawingReviewPage } from './DrawingReviewPage'
import { HomePage } from './HomePage'
import { LibraryPage } from './LibraryPage'
import { TeachPage } from './TeachPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/library" element={<LibraryPage />} />
      <Route path="/teach/:pageId" element={<TeachPage />} />
      <Route path="/drawing-review/:pageId" element={<DrawingReviewPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
