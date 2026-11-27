import { lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router';

import { AuthProvider } from './auth/AuthContext';
import { AnonymousOnly, RequireRole, RequireSession } from './auth/routes';
import { AppLayout } from './components/AppLayout';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { WaitingPage } from './pages/WaitingPage';
import { WelcomePage } from './pages/WelcomePage';
import { Providers } from './Providers';

// Pages most visits never open load on demand (their own chunks).
const ProfilePage = lazy(() =>
  import('./pages/ProfilePage').then((module) => ({ default: module.ProfilePage })),
);
const UsersPage = lazy(() =>
  import('./pages/admin/UsersPage').then((module) => ({ default: module.UsersPage })),
);
const DevicePage = lazy(() =>
  import('./pages/DevicePage').then((module) => ({ default: module.DevicePage })),
);
const HistoryPage = lazy(() =>
  import('./pages/HistoryPage').then((module) => ({ default: module.HistoryPage })),
);

export function AppRoutes() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<AnonymousOnly />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>
        <Route element={<RequireSession />}>
          <Route path="/welcome" element={<WelcomePage />} />
          <Route element={<AppLayout />}>
            <Route path="/waiting" element={<WaitingPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route element={<RequireRole min="admin" />}>
              <Route path="/admin/users" element={<UsersPage />} />
            </Route>
            <Route element={<RequireRole min="user" />}>
              <Route index element={<HomePage />} />
              <Route path="/devices/:id" element={<DevicePage />} />
              <Route path="/devices/:id/history" element={<HistoryPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default function App() {
  return (
    <Providers>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </Providers>
  );
}
