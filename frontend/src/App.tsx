import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/Toast";
import Home from "./pages/Home";
import JobView from "./pages/JobView";
import Gallery from "./pages/Gallery";
import Settings from "./pages/Settings";

// Note: no AnimatePresence around the routes. Exit animations require the
// outgoing page to finish animating before the next one mounts, and a page
// that re-renders continuously (JobView during a live job) can keep that
// exit from ever completing — leaving the next tab blank. Pages animate
// themselves on mount instead (see Page in Layout.tsx).
export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/jobs/:id" element={<JobView />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ToastProvider>
  );
}
