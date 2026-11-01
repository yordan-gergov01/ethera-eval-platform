/**
 * Paged table of the Products of every Client the user is a member of.
 *
 * Role: list view of the registry feature (client, project, generation model, Manifest version,
 *   last change).
 * Used by: pages/ProductsPage.tsx.
 * Depends on: ./use-products-page, ./paths, ErrorMessage, react-router Link.
 * Key invariants: a user with no Client Membership sees "You are not a member of any client."
 *   (the backend answers an empty list, never an error); while the next page loads the current one
 *   stays visible (aria-busy) and "Next" is disabled; identifiers and model IDs are plain text;
 *   dates use the browser's locale.
 */
import { Link } from 'react-router';

import { productPagePath } from './paths';
import { useProductsPage } from './use-products-page';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

const formatDate = (value: string) => new Date(value).toLocaleString();

/** One page of Products with paging controls. */
export function ProductsList() {
  const { query, page, pages, goTo } = useProductsPage();
  const { data, error, isPending, isPlaceholderData } = query;

  if (isPending) {
    return <p className="status">Loading…</p>;
  }
  if (error) {
    return <ErrorMessage error={error} />;
  }
  if (data.total === 0) {
    return <p className="status">You are not a member of any client.</p>;
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table aria-busy={isPlaceholderData}>
          <thead>
            <tr>
              <th scope="col">Client</th>
              <th scope="col">Project</th>
              <th scope="col">Generation model</th>
              <th scope="col">Manifest</th>
              <th scope="col">Last changed</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((product) => (
              <tr key={`${product.client_id}/${product.project_id}`}>
                <td>{product.client_id}</td>
                <td>
                  <Link to={productPagePath(product.client_id, product.project_id)}>
                    {product.project_id}
                  </Link>
                </td>
                <td>
                  <code>{product.generation_binding.model}</code>
                </td>
                <td>Version {product.manifest_version}</td>
                <td>
                  {formatDate(product.changed_at)} · {product.changed_by}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <nav aria-label="Pages" className="pagination">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => {
            goTo(page - 1);
          }}
        >
          Previous
        </button>
        <span>
          Page {page} of {pages} ({data.total} products)
        </span>
        <button
          type="button"
          disabled={page >= pages || isPlaceholderData}
          onClick={() => {
            goTo(page + 1);
          }}
        >
          Next
        </button>
      </nav>
    </>
  );
}
