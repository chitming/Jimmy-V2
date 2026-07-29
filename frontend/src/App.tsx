import { Navigate, Route, Routes } from 'react-router-dom'
import { HomePage } from './HomePage'
import { TeachPage } from './TeachPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/teach/:pageId" element={<TeachPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
