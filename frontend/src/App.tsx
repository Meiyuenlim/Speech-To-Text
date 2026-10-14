import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { NewMeetingPage } from "./pages/NewMeetingPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ReviewPage } from "./pages/ReviewPage";

export function App() {
  return <BrowserRouter><Routes><Route element={<Layout />}><Route path="/" element={<DashboardPage />} /><Route path="/new" element={<NewMeetingPage />} /><Route path="/meetings/:id/process" element={<ProcessingPage />} /><Route path="/meetings/:id/review" element={<ReviewPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></BrowserRouter>;
}
