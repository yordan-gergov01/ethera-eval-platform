/**
 * Page for one Product.
 *
 * Role: reads the client and project IDs from the URL and composes ProductDetail under a
 *   breadcrumb back to the list.
 * Used by: routes/router.tsx (products/:clientId/:projectId).
 * Depends on: features/registry/ProductDetail, react-router useParams and Link.
 * Key invariants: ProductDetail is keyed by both IDs so moving between Products resets its state;
 *   the heading is rendered by ProductDetail once the Product is loaded; the products:read check
 *   lives in the router.
 */
import { Link, useParams } from 'react-router';

import { ProductDetail } from '@/features/registry/ProductDetail';

export function ProductPage() {
  const { clientId = '', projectId = '' } = useParams();

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-2 text-sm text-gray-600">
        <Link to="/products">Products</Link> / {clientId}
      </nav>
      <ProductDetail key={`${clientId}/${projectId}`} clientId={clientId} projectId={projectId} />
    </>
  );
}
