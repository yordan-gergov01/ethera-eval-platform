/**
 * Mutation hook that saves the user's own name and email.
 *
 * Role: calls updateProfile and writes the returned user into the session's `me` query cache.
 * Used by: features/profile/ProfileForm.tsx.
 * Depends on: ./api updateProfile, meQueryOptions from providers/auth/session-api, TanStack Query.
 * Key invariants: sets the `me` cache from the response (no refetch) so the header shows the change
 *   at once.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { updateProfile } from './api';
import { meQueryOptions } from '@/providers/auth/session-api';

/** Saves name and email and updates the session's user, so the header shows the change at once. */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryOptions.queryKey, me);
    },
  });
}
