import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "../features/home/HomePage";
import { AppShell } from "./AppShell";


const PlansPage = lazy(() => import("../features/plans/PlansPage").then((module) => ({ default: module.PlansPage })));
const A1TraceReviewPage = lazy(() => import("../features/plans/A1TraceReviewPage").then((module) => ({ default: module.A1TraceReviewPage })));
const ReviewPage = lazy(() => import("../features/review/ReviewPage").then((module) => ({ default: module.ReviewPage })));
const ModelPage = lazy(() => import("../features/model/ModelPage").then((module) => ({ default: module.ModelPage })));
const RenderPage = lazy(() => import("../features/render/RenderPage").then((module) => ({ default: module.RenderPage })));
const ReportPage = lazy(() => import("../features/report/ReportPage").then((module) => ({ default: module.ReportPage })));
const TourPage = lazy(() => import("../features/tour/TourPage").then((module) => ({ default: module.TourPage })));


export function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Suspense fallback={<main className="workspace-page"><p className="page-message" role="status">Opening your project…</p></main>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/projects/:projectId/plans" element={<PlansPage />} />
            <Route path="/projects/:projectId/a1-trace" element={<A1TraceReviewPage />} />
            <Route path="/projects/:projectId/review" element={<ReviewPage />} />
            <Route path="/projects/:projectId/model" element={<ModelPage />} />
            <Route path="/projects/:projectId/render" element={<RenderPage />} />
            <Route path="/projects/:projectId/report" element={<ReportPage />} />
            <Route path="/tour-spike" element={<TourPage />} />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </Suspense>
      </AppShell>
    </BrowserRouter>
  );
}
