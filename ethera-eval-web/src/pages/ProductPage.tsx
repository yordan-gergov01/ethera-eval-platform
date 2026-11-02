/**
 * Page for one Product.
 *
 * Role: reads the client and project IDs from the URL and composes the registry's ProductDetail
 *   and the evaluation feature's DatasetSummary under a breadcrumb back to the list (PP-210).
 * Used by: routes/router.tsx (products/:clientId/:projectId).
 * Depends on: features/registry/ProductDetail, features/evaluation/DatasetSummary, react-router
 *   useParams and Link.
 * Key invariants: the two features never import each other, this page composes them;
 *   ProductDetail and DatasetSummary are keyed by both IDs so moving between Products resets them;
 *   the heading is rendered by ProductDetail once the Product is loaded; the products:read check
 *   lives in the router.
 */
import { Link, useParams } from 'react-router';

import { DatasetSummary } from '@/features/evaluation/DatasetSummary';
import { ProductDetail } from '@/features/registry/ProductDetail';

export function ProductPage() {
  const { clientId = '', projectId = '' } = useParams();

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-2 text-sm text-gray-600">
        <Link to="/products">Products</Link> / {clientId}
      </nav>
      <ProductDetail key={`${clientId}/${projectId}`} clientId={clientId} projectId={projectId} />
      <DatasetSummary
        key={`${clientId}/${projectId}/dataset`}
        clientId={clientId}
        projectId={projectId}
      />
    </>
  );
}
