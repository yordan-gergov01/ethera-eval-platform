/**
 * Page for one Product's Dataset.
 *
 * Role: reads the client and project IDs from the URL and composes the evaluation feature's
 *   DatasetVersion under a breadcrumb back to the Product.
 * Used by: routes/router.tsx (products/:clientId/:projectId/dataset).
 * Depends on: features/evaluation/DatasetVersion, features/registry/paths, react-router
 *   useParams and Link.
 * Key invariants: DatasetVersion is keyed by both IDs so moving between Products resets its state;
 *   the chosen version lives in `?version=` and is read by the feature; the products:read check
 *   lives in the router (the backend checks too).
 */
import { Link, useParams } from 'react-router';

import { DatasetVersion } from '@/features/evaluation/DatasetVersion';
import { productPagePath } from '@/features/registry/paths';

export function DatasetPage() {
  const { clientId = '', projectId = '' } = useParams();

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-2 text-sm text-gray-600">
        <Link to="/products">Products</Link> / {clientId} /{' '}
        <Link to={productPagePath(clientId, projectId)}>{projectId}</Link>
      </nav>
      <h1>Dataset of {projectId}</h1>
      <DatasetVersion key={`${clientId}/${projectId}`} clientId={clientId} projectId={projectId} />
    </>
  );
}
