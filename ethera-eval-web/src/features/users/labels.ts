/**
 * Label map for user roles.
 *
 * Role: English labels for the built-in roles shown on the users pages (D-012).
 * Used by: features/users UsersList, CreateUserForm, EditUserForm; labels.test.ts.
 * Depends on: the RoleName type from lib/api/types (generated from the backend's enum).
 * Key invariants: typed `Record<RoleName, string>`, so a role the backend adds fails the type check
 *   until it has a label; a role name the map does not know is shown raw, never hidden. Labels
 *   are for display only; the UI never decides access by role (permissions only).
 */
import type { RoleName } from '@/lib/api/types';

export const ROLE_LABELS: Record<RoleName, string> = {
  admin: 'Administrator',
  user: 'User',
};

/** The label of a role name, or the name itself when the map does not know it. */
export function roleLabel(name: string): string {
  return Object.hasOwn(ROLE_LABELS, name) ? ROLE_LABELS[name as RoleName] : name;
}
