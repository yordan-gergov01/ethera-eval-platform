/**
 * Route guard that shows a page only with a permission.
 *
 * Role: renders the page or NotAllowedPage.
 * Used by: routes/router.tsx (PROTECTED_PAGES entries with a permission).
 * Depends on: useAuth().can, pages/NotAllowedPage, Permission type.
 * Key invariants: this only hides pages in the UI; the backend still checks every request.
 */
import type { ReactNode } from 'react';

import type { Permission } from '@/lib/api/types';
import { NotAllowedPage } from '@/pages/NotAllowedPage';
import { useAuth } from '@/providers/auth/auth-context';

export interface RequirePermissionProps {
  permission: Permission;
  children: ReactNode;
}

/** Shows the page only with the permission; the backend still checks every request. */
export function RequirePermission({ permission, children }: RequirePermissionProps) {
  const { can } = useAuth();
  return can(permission) ? children : <NotAllowedPage />;
}
