/**
 * Mutation hook that changes the user's own password.
 *
 * Role: calls changePassword, then ends the local session with reason 'password-changed'.
 * Used by: features/profile/PasswordForm.tsx.
 * Depends on: ./api changePassword, useAuth().endSession.
 * Key invariants: calls endSession, not logout: the backend has already ended every session, so
 *   only local state is cleared (template_web D-003).
 */
import { useMutation } from '@tanstack/react-query';

import { changePassword } from './api';
import { useAuth } from '@/providers/auth/auth-context';

/**
 * Changes the password. The backend then ends every session of the user, so
 * the local session ends too and the login page asks for the new password.
 */
export function useChangePassword() {
  const { endSession } = useAuth();
  return useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      endSession('password-changed');
    },
  });
}
