/**
 * Page with the list of Products.
 *
 * Role: composes ProductsList under a heading; the landing page after sign-in.
 * Used by: routes/router.tsx (products, and the '/' redirect).
 * Depends on: features/registry/ProductsList.
 * Key invariants: the products:read check lives in the router (RequirePermission), not here.
 */
import { ProductsList } from '@/features/registry/ProductsList';

export function ProductsPage() {
  return (
    <>
      <h1>Products</h1>
      <p className="status">Products of the clients you are a member of.</p>
      <ProductsList />
    </>
  );
}
