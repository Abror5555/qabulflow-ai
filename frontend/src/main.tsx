import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { FiltersProvider } from "./contexts/FiltersContext";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { ToastProvider } from "./contexts/ToastContext";
import { ApiError } from "./lib/api";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && count < 2,
      refetchOnWindowFocus: false,
    },
  },
});

/** Server tomonida saqlangan mavzu tanlovini (boshqa qurilmadan) qo'llash. */
function ThemeSync() {
  const { me } = useAuth();
  const { choice, setChoice } = useTheme();
  const remote = me?.preferences?.theme;
  useEffect(() => {
    if (remote && remote !== choice) setChoice(remote, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remote]);
  return null;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <FiltersProvider>
                <ThemeSync />
                <App />
              </FiltersProvider>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
