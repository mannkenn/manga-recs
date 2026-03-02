import nextPlugin from '@next/eslint-plugin-next';
import js from '@eslint/js';

export default [
  {
    ignores: ['.next/**', 'node_modules/**', 'out/**', 'build/**'],
  },
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    plugins: {
      '@next/next': nextPlugin,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs['core-web-vitals'].rules,
      'react/no-unescaped-entities': 'off',
      '@next/next/no-html-link-for-pages': 'off',
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        React: 'readonly',
      },
    },
  },
];
