/**
 * Browser paths of the registry pages.
 *
 * Role: builds the links to a Product page and its Replace Manifest page.
 * Used by: features/registry ProductsList, ProductDetail, ReplaceManifestForm;
 *   pages/ReplaceManifestPage.tsx, pages/DatasetPage.tsx; paths.test.ts.
 * Depends on: nothing.
 * Key invariants: both identifiers are URL-encoded; the shapes match the routes in
 *   routes/router.tsx (`products/:clientId/:projectId` and `.../manifest`).
 */

/** The browser path of one Product's page. */
export function productPagePath(clientId: string, projectId: string): string {
  return `/products/${encodeURIComponent(clientId)}/${encodeURIComponent(projectId)}`;
}

/** The browser path of one Product's Replace Manifest page. */
export function replaceManifestPagePath(clientId: string, projectId: string): string {
  return `${productPagePath(clientId, projectId)}/manifest`;
}
