import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Home from "./pages/Home";
import History from "./pages/History";
import JobDetail from "./pages/JobDetail";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
            <Link to="/" className="font-bold text-xl tracking-tight">
              Clip<span className="text-amber-400">Mine</span>
            </Link>
            <nav className="flex gap-6 text-sm text-zinc-400">
              <Link to="/" className="hover:text-white transition">
                New Mine
              </Link>
              <Link to="/history" className="hover:text-white transition">
                History
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/history" element={<History />} />
            <Route path="/jobs/:id" element={<JobDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
