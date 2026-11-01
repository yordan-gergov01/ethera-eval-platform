/**
 * Page for replacing one Product's Manifest.
 *
 * Role: reads the client and project IDs from the URL and composes ReplaceManifestForm under a
 *   breadcrumb.
 * Used by: routes/router.tsx (products/:clientId/:projectId/manifest).
 * Depends on: features/registry/ReplaceManifestForm and paths, react-router useParams and Link.
 * Key invariants: the form is keyed by both IDs so its captured base version never leaks to
 *   another Product; the manifests:write check lives in the router (the backend checks too).
 */
import { Link, useParams } from 'react-router';

import { productPagePath } from '@/features/registry/paths';
import { ReplaceManifestForm } from '@/features/registry/ReplaceManifestForm';

export function ReplaceManifestPage() {
  const { clientId = '', projectId = '' } = useParams();

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-2 text-sm text-gray-600">
        <Link to="/products">Products</Link> / {clientId} /{' '}
        <Link to={productPagePath(clientId, projectId)}>{projectId}</Link>
      </nav>
      <h1>Replace Manifest</h1>
      <ReplaceManifestForm
        key={`${clientId}/${projectId}`}
        clientId={clientId}
        projectId={projectId}
      />
    </>
  );
}
