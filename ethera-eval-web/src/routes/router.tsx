/**
 * The app's routes, their guards and the navigation.
 *
 * Role: defines the browser router.
 * Used by: src/App.tsx (RouterProvider).
 * Depends on: react-router createBrowserRouter, ./RequireAuth, ./RequirePermission,
 *   components/layout/AppShell, pages/*.
 * Key invariants: PROTECTED_PAGES is the single list that drives the routes, their permission
 *   guards and the navigation; only pages with a label appear in the navigation; '/' redirects to
 *   /profile; RouteErrorPage is the error element of every route.
 */
import type { ReactNode } from 'react';
import { Navigate, createBrowserRouter } from 'react-router';

import { RequireAuth } from './RequireAuth';
import { RequirePermission } from './RequirePermission';
import { AppShell, type NavItem } from '@/components/layout/AppShell';
import type { Permission } from '@/lib/api/types';
import { LoginPage } from '@/pages/LoginPage';
import { NewUserPage } from '@/pages/NewUserPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { RouteErrorPage } from '@/pages/RouteErrorPage';
import { UserDetailPage } from '@/pages/UserDetailPage';
import { UsersPage } from '@/pages/UsersPage';

interface ProtectedPage {
  path: string;
  /** Pages with a label appear in the navigation. */
  label?: string;
  permission?: Permission;
  element: ReactNode;
}

/** Pages for signed-in users. The same list drives the routes, their guards and the navigation. */
const PROTECTED_PAGES: readonly ProtectedPage[] = [
  { path: 'profile', label: 'Profile', element: <ProfilePage /> },
  { path: 'users', label: 'Users', permission: 'users:read', element: <UsersPage /> },
  { path: 'users/new', permission: 'users:create', element: <NewUserPage /> },
  { path: 'users/:userId', permission: 'users:read', element: <UserDetailPage /> },
];

const navItems: NavItem[] = PROTECTED_PAGES.flatMap(({ path, label, permission }) =>
  label ? [{ to: `/${path}`, label, permission }] : [],
);

export const router = createBrowserRouter([
  {
    errorElement: <RouteErrorPage />,
    children: [
      { path: '/login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppShell navItems={navItems} />,
            children: [
              { index: true, element: <Navigate to="/profile" replace /> },
              ...PROTECTED_PAGES.map(({ path, permission, element }) => ({
                path,
                element: permission ? (
                  <RequirePermission permission={permission}>{element}</RequirePermission>
                ) : (
                  element
                ),
              })),
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]);
