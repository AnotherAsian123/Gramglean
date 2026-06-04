import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import JobView from "./pages/JobView";
import Gallery from "./pages/Gallery";
import Settings from "./pages/Settings";
import { api } from "./lib/api";

export default function App() {
  // Apply the saved theme as early as possible.
  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        const root = document.documentElement;
        root.classList.toggle("light", s.theme === "light");
        root.classList.toggle("dark", s.theme !== "light");
      })
      .catch(() => {});
  }, []);

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/jobs/:id" element={<JobView />} />
        <Route path="/gallery" element={<Gallery />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </Layout>
  );
}
