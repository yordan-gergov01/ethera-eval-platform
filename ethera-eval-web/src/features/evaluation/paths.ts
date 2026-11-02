/**
 * Browser paths of the evaluation pages.
 *
 * Role: builds the link to a Product's Dataset page, optionally at one Dataset version.
 * Used by: features/evaluation DatasetSummary and DatasetVersion; paths.test.ts.
 * Depends on: nothing.
 * Key invariants: both identifiers are URL-encoded; the shape matches the route in
 *   routes/router.tsx (`products/:clientId/:projectId/dataset`, version as `?version=`); the
 *   Product part restates the registry's page path because features never import each other.
 */

/** The browser path of a Product's Dataset page; without a version it shows the current one. */
export function datasetPagePath(clientId: string, projectId: string, version?: number): string {
  const path = `/products/${encodeURIComponent(clientId)}/${encodeURIComponent(projectId)}/dataset`;
  return version === undefined ? path : `${path}?version=${String(version)}`;
}
