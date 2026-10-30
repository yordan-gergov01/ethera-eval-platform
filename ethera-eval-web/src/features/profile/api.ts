/**
 * Backend calls of the profile feature.
 *
 * Role: PATCH /api/v1/users/me and POST /api/v1/users/me/password.
 * Used by: features/profile/use-update-profile.ts, features/profile/use-change-password.ts.
 * Depends on: api from lib/api/http; Me, PasswordChange and UserSelfUpdate types.
 * Key invariants: a successful password change (204) ends every session of the user on the backend,
 *   so the caller ends the local session; features never import each other (template_web D-001).
 */
import { api } from '@/lib/api/http';
import type { Me, PasswordChange, UserSelfUpdate } from '@/lib/api/types';

export function updateProfile(changes: UserSelfUpdate) {
  return api.patch<Me>('/api/v1/users/me', { json: changes });
}

/** Ends every session of the user on success (204). */
export function changePassword(body: PasswordChange) {
  return api.post<undefined>('/api/v1/users/me/password', { json: body });
}
