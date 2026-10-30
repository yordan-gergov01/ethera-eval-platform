import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// Feature modules under src/features/. Each one may import itself, shared code
// and providers, never another feature.
const FEATURES = ['auth', 'profile', 'users'];

// An import path group for a top-level folder under src/ and everything in it.
const folder = (name) => [`@/${name}`, `@/${name}/**`];

const restrictImports = (patterns) => ({
  'no-restricted-imports': ['error', { patterns }],
});

// Cross-folder imports use the @/ alias so the rules below can see the target
// folder in the import path; relative imports stay within one folder.
const noParentImports = {
  group: ['../*', '../**'],
  message: 'Import from another folder through the @/ alias.',
};

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/lib/api/schema.gen.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      'no-console': 'error',
      ...restrictImports([noParentImports]),
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [reactHooks.configs.flat['recommended-latest'], reactRefresh.configs.vite],
    languageOptions: { globals: globals.browser },
    rules: {
      // Styles come only from the built stylesheet, so the production CSP can
      // keep style-src 'self' without 'unsafe-inline'.
      'no-restricted-syntax': [
        'error',
        {
          selector: "JSXAttribute[name.name='style']",
          message: 'Use Tailwind classes; inline styles break the style-src CSP.',
        },
        {
          selector: "JSXOpeningElement[name.name='style']",
          message: 'Put styles in src/assets/index.css; <style> elements break the style-src CSP.',
        },
      ],
    },
  },
  ...FEATURES.map((feature) => ({
    files: [`src/features/${feature}/**/*.{ts,tsx}`],
    rules: restrictImports([
      noParentImports,
      {
        group: ['@/features/*', `!@/features/${feature}`, `!@/features/${feature}/**`],
        message: 'Features never import other features; compose them in a page.',
      },
      {
        group: [...folder('pages'), ...folder('routes')],
        message: 'Features import only shared code and providers.',
      },
    ]),
  })),
  {
    // Shared React code may use the session and other providers.
    files: ['src/{components,hooks}/**/*.{ts,tsx}'],
    rules: restrictImports([
      noParentImports,
      {
        group: [...folder('features'), ...folder('pages'), ...folder('routes')],
        message: 'Shared code never depends on features, pages or routes.',
      },
    ]),
  },
  {
    // Framework-free shared code sits below the providers, which import it.
    files: ['src/{lib,utils,config,types}/**/*.{ts,tsx}'],
    rules: restrictImports([
      noParentImports,
      {
        group: [
          ...folder('features'),
          ...folder('pages'),
          ...folder('routes'),
          ...folder('providers'),
        ],
        message:
          'lib, utils, config and types never depend on features, pages, routes or providers.',
      },
    ]),
  },
  {
    files: ['src/providers/**/*.{ts,tsx}'],
    rules: restrictImports([
      noParentImports,
      {
        group: [
          ...folder('features'),
          ...folder('pages'),
          ...folder('routes'),
          ...folder('components'),
          ...folder('hooks'),
        ],
        message: 'Providers import only from lib, config, utils and types.',
      },
    ]),
  },
  {
    files: ['**/*.{js,mjs}'],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
    rules: { 'no-console': 'error' },
  },
);
