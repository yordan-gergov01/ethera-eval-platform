/**
 * Mechanical guard: every source file opens with the four-part header.
 *
 * Role: enforces the Bible's docstring rule (.claude/rules/code-quality.md) for TypeScript,
 *   so the boundary signage cannot silently decay.
 * Used by: `npm test` (and therefore `npm run check` and CI).
 * Depends on: Vite's `import.meta.glob` with `?raw` to read every file under src/.
 * Key invariants: the generated `src/lib/api/schema.gen.ts` is the only exemption; the four
 *   labels must appear in order inside the leading block comment; the negative cases below
 *   prove the guard fires.
 */
import { describe, expect, it } from 'vitest';

const LABELS = ['Role:', 'Used by:', 'Depends on:', 'Key invariants:'] as const;
const EXEMPT = new Set(['/src/lib/api/schema.gen.ts']);

/** The missing or out-of-order labels of a file's leading block comment; empty when valid. */
export function headerProblems(source: string): string[] {
  const match = /^\s*\/\*\*([\s\S]*?)\*\//.exec(source);
  if (!match?.[1]) {
    return ['no leading /** ... */ block'];
  }
  const block = match[1];
  const problems: string[] = [];
  let cursor = -1;
  for (const label of LABELS) {
    const at = block.indexOf(label);
    if (at === -1) {
      problems.push(`missing "${label}"`);
    } else if (at < cursor) {
      problems.push(`"${label}" out of order`);
    } else {
      cursor = at;
    }
  }
  return problems;
}

const SOURCES = import.meta.glob<string>('/src/**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('file headers', () => {
  it('finds the source files', () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(10);
  });

  it('every source file opens with Role / Used by / Depends on / Key invariants', () => {
    const offenders = Object.entries(SOURCES)
      .filter(([path]) => !EXEMPT.has(path))
      .map(([path, source]) => [path, headerProblems(source)] as const)
      .filter(([, problems]) => problems.length > 0)
      .map(([path, problems]) => `${path}: ${problems.join(', ')}`);
    expect(offenders).toEqual([]);
  });

  it('fires on a file without a header', () => {
    expect(headerProblems("import x from 'y';\n")).toEqual(['no leading /** ... */ block']);
  });

  it('fires on a missing or misordered label', () => {
    expect(headerProblems('/** Role: a\n Used by: b\n Key invariants: c */')).toEqual([
      'missing "Depends on:"',
    ]);
    expect(
      headerProblems('/** Used by: b\n Role: a\n Depends on: c\n Key invariants: d */'),
    ).toEqual(['"Used by:" out of order']);
  });

  it('accepts a complete header', () => {
    expect(
      headerProblems(
        '/**\n * x\n * Role: a\n * Used by: b\n * Depends on: c\n * Key invariants: d\n */',
      ),
    ).toEqual([]);
  });
});
