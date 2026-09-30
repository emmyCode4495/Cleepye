import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { MineProvider } from "./context/MineContext";
import { NoticeProvider } from "./context/NoticeContext";
import { ToastProvider } from "./context/ToastContext";
import Home from "./pages/Home";
import Mine from "./pages/Mine";
import History from "./pages/History";
import JobDetail from "./pages/JobDetail";
import Auth from "./pages/Auth";
import Pricing from "./pages/Pricing";
import Contact from "./pages/Contact";
import Download from "./pages/Download";
import Profile from "./pages/Profile";
import NotFound from "./pages/NotFound";
import type { ReactNode } from "react";


function HomeOrRedirect() {
  const auth = useAuth();
  if (auth.configured && !auth.loading && auth.user) {
    return <Navigate to="/mine" replace />;
  }
  return <Home />;
}

function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth();
  if (!auth.configured) return <>{children}</>;
  if (auth.loading) return <p className="p-8 text-sm text-dim">Loading…</p>;
  if (!auth.user) return <Navigate to="/auth" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <NoticeProvider>
          <AuthProvider>
            <MineProvider>
              <Routes>
                <Route path="/auth" element={<Auth />} />
                <Route element={<Layout />}>
                  <Route index element={<HomeOrRedirect />} />
                  <Route path="mine" element={<Mine />} />
                  <Route path="pricing" element={<Pricing />} />
                  <Route path="contact" element={<Contact />} />
                  <Route path="download" element={<Download />} />
                  <Route
                    path="history"
                    element={
                      <RequireAuth>
                        <History />
                      </RequireAuth>
                    }
                  />
                  <Route
                    path="profile"
                    element={
                      <RequireAuth>
                        <Profile />
                      </RequireAuth>
                    }
                  />
                  <Route
                    path="jobs/:id"
                    element={
                      <RequireAuth>
                        <JobDetail />
                      </RequireAuth>
                    }
                  />
                  <Route path="*" element={<NotFound />} />
                </Route>
              </Routes>
            </MineProvider>
          </AuthProvider>
        </NoticeProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
