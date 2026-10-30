/**
 * The permission check behind `can()`.
 *
 * Role: decides whether the current user's permissions include one.
 * Used by: providers/auth/AuthProvider.tsx, permissions.test.ts.
 * Depends on: Permission type.
 * Key invariants: the UI decides by permission only, never by role name; unknown permissions mean
 *   false; the backend remains the authority.
 */
import type { Permission } from '@/lib/api/types';

/**
 * Whether the permissions from /users/me include the given one. The UI decides
 * by permission only, never by role name; the backend remains the authority.
 */
export function hasPermission(
  permissions: readonly Permission[] | undefined,
  permission: Permission,
): boolean {
  return permissions?.includes(permission) ?? false;
}
