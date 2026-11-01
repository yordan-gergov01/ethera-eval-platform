/**
 * Profile page of the signed-in user.
 *
 * Role: shows username and role and composes ProfileForm and PasswordForm.
 * Used by: routes/router.tsx (profile).
 * Depends on: features/profile ProfileForm and PasswordForm, useAuth.
 * Key invariants: ProfileForm is keyed by the user id so its fields reset for another user; renders
 *   nothing while no user is loaded.
 */
import { PasswordForm } from '@/features/profile/PasswordForm';
import { ProfileForm } from '@/features/profile/ProfileForm';
import { useAuth } from '@/providers/auth/auth-context';

export function ProfilePage() {
  const { user } = useAuth();
  if (!user) {
    return null;
  }

  return (
    <>
      <h1>Profile</h1>
      <dl className="details">
        <dt>Username</dt>
        <dd>{user.username}</dd>
        <dt>Role</dt>
        <dd>{user.role}</dd>
      </dl>

      <h2>Name and email</h2>
      <ProfileForm key={user.id} user={user} />

      <h2>Password</h2>
      <PasswordForm />
    </>
  );
}
