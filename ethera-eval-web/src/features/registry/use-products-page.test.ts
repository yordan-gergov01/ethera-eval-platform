/**
 * Unit tests for the Products page hook.
 *
 * Role: proves a missing or invalid ?page means page 1, a valid one is read as given, the page
 *   asks for the matching offset, `pages` is at least 1 (also for an empty list) and rounds up,
 *   and goTo writes page 1 as no parameter and any other page as ?page=N.
 * Used by: Vitest.
 * Depends on: ./use-products-page, ./api (PAGE_SIZE, productsPageQueryOptions),
 *   react-dom/server renderToStaticMarkup, react-router MemoryRouter (reads are real) with
 *   `useSearchParams`'s setter replaced by a spy, TanStack Query; the global fetch and window
 *   config stubbed (the backend is external).
 * Key invariants: the hook runs inside a statically rendered probe; the page is fetched through
 *   the real query options and `api` client before rendering, so `pages` comes from a real cached
 *   answer and a wrong offset would miss the cache; writing the URL cannot be observed without a
 *   DOM (react-router navigates only after a layout effect), so the setter of `useSearchParams` —
 *   a third-party library, not our code — is the one thing replaced.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PAGE_SIZE, productsPageQueryOptions } from './api';
import { useProductsPage } from './use-products-page';

const setParams = vi.hoisted(() => vi.fn());

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>();
  return {
    ...actual,
    useSearchParams: () => [actual.useSearchParams()[0], setParams] as const,
  };
});

beforeEach(() => {
  setParams.mockClear();
  vi.stubGlobal('window', { __APP_CONFIG__: { backendUrl: 'http://backend:8000' } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Caches the page at `offset` from a backend holding `total` Products, then renders the hook. */
async function renderAt(search: string, total: number, offset: number) {
  const body = JSON.stringify({ items: [], total, limit: PAGE_SIZE, offset });
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    ),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false } },
  });
  await queryClient.query(productsPageQueryOptions(offset));
  let result: ReturnType<typeof useProductsPage> | undefined;
  function Probe() {
    result = useProductsPage();
    return null;
  }
  renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(MemoryRouter, { initialEntries: [`/products${search}`] }, createElement(Probe)),
    ),
  );
  if (!result) {
    throw new Error('the probe did not render');
  }
  return result;
}

describe('useProductsPage', () => {
  it.each(['', '?page=', '?page=abc', '?page=0', '?page=-1', '?page=1.5'])(
    'reads %j as page 1',
    async (search) => {
      const page = await renderAt(search, 45, 0);

      expect(page.page).toBe(1);
      expect(page.query.data?.offset).toBe(0);
    },
  );

  it('reads a valid page as given and asks for its offset', async () => {
    const page = await renderAt('?page=3', 45, 2 * PAGE_SIZE);

    expect(page.page).toBe(3);
    expect(page.query.data?.offset).toBe(2 * PAGE_SIZE);
  });

  it('counts pages rounding up, and at least one for an empty list', async () => {
    expect((await renderAt('', 45, 0)).pages).toBe(3);
    expect((await renderAt('', 40, 0)).pages).toBe(2);
    expect((await renderAt('', 0, 0)).pages).toBe(1);
  });

  it('goTo writes page 1 as no parameter', async () => {
    (await renderAt('?page=2', 45, PAGE_SIZE)).goTo(1);

    expect(setParams).toHaveBeenCalledExactlyOnceWith({});
  });

  it('goTo writes any other page as the page param', async () => {
    (await renderAt('', 45, 0)).goTo(3);

    expect(setParams).toHaveBeenCalledExactlyOnceWith({ page: '3' });
  });
});
