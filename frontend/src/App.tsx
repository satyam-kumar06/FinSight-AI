import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import Home from './pages/Home'
import Analyze from './pages/Analyze'
import ProductSearch from './pages/ProductSearch'
import Market from './pages/Market'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/products" element={<ProductSearch />} />
          <Route path="/market" element={<Market />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App