import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Spinner } from "./components/ui/States";
import { useAuth } from "./contexts/AuthContext";
import type { Role } from "./lib/types";

const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const LeadsPage = lazy(() => import("./pages/LeadsPage"));
const ConversationsPage = lazy(() => import("./pages/ConversationsPage"));
const BookingsPage = lazy(() => import("./pages/BookingsPage"));
const CoursesPage = lazy(() => import("./pages/CoursesPage"));
const KnowledgePage = lazy(() => import("./pages/KnowledgePage"));
const AISettingsPage = lazy(() => import("./pages/AISettingsPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const TeamPage = lazy(() => import("./pages/TeamPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const WebchatPage = lazy(() => import("./pages/WebchatPage"));

function FullScreenLoader() {
  return (
    <div className="flex h-full items-center justify-center">
      <Spinner />
    </div>
  );
}

function Protected({ children, role }: { children: ReactNode; role?: Role }) {
  const { me, loading, can } = useAuth();
  const location = useLocation();
  if (loading) return <FullScreenLoader />;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (role && !can(role)) {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-20 text-center">
          <p className="text-lg font-semibold text-ink">Bu bo'lim sizning rolingiz uchun yopiq</p>
          <p className="mt-1 text-sm text-ink-3">Kirish huquqi uchun tashkilot egasiga murojaat qiling.</p>
        </div>
      </AppShell>
    );
  }
  return (
    <AppShell>
      <Suspense fallback={<FullScreenLoader />}>{children}</Suspense>
    </AppShell>
  );
}

function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
      <p className="text-5xl font-semibold text-ink-3">404</p>
      <p className="text-ink">Sahifa topilmadi</p>
      <a href="/" className="text-sm font-medium text-accent hover:underline">
        Bosh sahifaga qaytish
      </a>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/chat/:publicKey" element={<WebchatPage />} />
        <Route path="/" element={<Protected><OverviewPage /></Protected>} />
        <Route path="/leads" element={<Protected><LeadsPage /></Protected>} />
        <Route path="/conversations" element={<Protected><ConversationsPage /></Protected>} />
        <Route path="/conversations/:id" element={<Protected><ConversationsPage /></Protected>} />
        <Route path="/bookings" element={<Protected><BookingsPage /></Protected>} />
        <Route path="/courses" element={<Protected><CoursesPage /></Protected>} />
        <Route path="/knowledge" element={<Protected><KnowledgePage /></Protected>} />
        <Route path="/ai" element={<Protected><AISettingsPage /></Protected>} />
        <Route path="/analytics" element={<Protected role="manager"><AnalyticsPage /></Protected>} />
        <Route path="/team" element={<Protected role="manager"><TeamPage /></Protected>} />
        <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
