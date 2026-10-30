/**
 * Mutation hook that saves changes to one user.
 *
 * Role: PATCHes the user, stores the answer in its detail cache and refreshes the list pages.
 * Used by: features/users/EditUserForm.tsx.
 * Depends on: ./api updateUser, userQueryOptions and USERS_KEY; meQueryOptions from
 *   providers/auth/session-api.
 * Key invariants: when the edited user is the signed-in user, the session's `me` query is
 *   invalidated too, so the header and permissions catch up.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { USERS_KEY, updateUser, userQueryOptions } from './api';
import type { UserAdminUpdate } from '@/lib/api/types';
import { meQueryOptions } from '@/providers/auth/session-api';

/**
 * Saves changes to a user and refreshes what shows them: the user itself, the
 * list pages, and the session's user when someone edits their own record.
 */
export function useUpdateUser(userId: string, isSelf: boolean) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (changes: UserAdminUpdate) => updateUser(userId, changes),
    onSuccess: async (updated) => {
      queryClient.setQueryData(userQueryOptions(userId).queryKey, updated);
      await queryClient.invalidateQueries({ queryKey: [...USERS_KEY, 'page'] });
      if (isSelf) {
        await queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey });
      }
    },
  });
}
