/**
 * Page frame for signed-in users: header with navigation, user name and logout.
 *
 * Role: layout route element; child pages render through <Outlet />.
 * Used by: routes/router.tsx (layout route inside RequireAuth, nav items built from
 *   PROTECTED_PAGES).
 * Depends on: react-router NavLink/Outlet, useAuth (user, can, logout) from
 *   providers/auth/auth-context, Permission type.
 * Key invariants: nav items with a permission show only when can() allows it (cosmetic: the backend
 *   checks every request); logout is fire-and-forget because AuthProvider clears local state
 *   whatever the backend answers (template_web D-003).
 */
import { NavLink, Outlet } from 'react-router';

import type { Permission } from '@/lib/api/types';
import { useAuth } from '@/providers/auth/auth-context';

export interface NavItem {
  to: string;
  label: string;
  /** Shown only to users with this permission. */
  permission?: Permission;
}

export interface AppShellProps {
  navItems: readonly NavItem[];
}

/** Page frame for signed-in users; the navigation shows only what the user may use. */
export function AppShell({ navItems }: AppShellProps) {
  const { user, can, logout } = useAuth();
  const visible = navItems.filter((item) => !item.permission || can(item.permission));

  return (
    <>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-3">
          <nav aria-label="Main" className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            {visible.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className="rounded-sm text-gray-600 hover:text-gray-900 hover:no-underline aria-[current=page]:font-semibold aria-[current=page]:text-gray-900"
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-sm text-gray-700">
            <span>{user?.full_name}</span>
            <button
              type="button"
              className="border border-gray-300 bg-white px-3 py-1.5 text-gray-700 hover:bg-gray-100"
              onClick={() => {
                void logout();
              }}
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main>
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-xs sm:p-6">
          <Outlet />
        </div>
      </main>
    </>
  );
}
