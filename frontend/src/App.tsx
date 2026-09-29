import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { MineProvider } from "./context/MineContext";
import { ToastProvider } from "./context/ToastContext";
import Home from "./pages/Home";
import History from "./pages/History";
import JobDetail from "./pages/JobDetail";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <MineProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path="history" element={<History />} />
              <Route path="jobs/:id" element={<JobDetail />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </MineProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
