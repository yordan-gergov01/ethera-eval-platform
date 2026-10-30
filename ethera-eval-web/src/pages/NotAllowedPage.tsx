/**
 * Page shown instead of a page the user lacks the permission for.
 *
 * Role: static "Not allowed" message.
 * Used by: routes/RequirePermission.tsx.
 * Depends on: nothing beyond JSX.
 * Key invariants: none.
 */
export function NotAllowedPage() {
  return (
    <>
      <h1>Not allowed</h1>
      <p>You are not allowed to open this page.</p>
    </>
  );
}
