import next from 'eslint-config-next';

// Flat config, because `next lint` was removed in Next 16 and ESLint 10 no
// longer reads .eslintrc. `eslint-config-next` default-exports a flat array,
// so it spreads straight in.
const config = [
  { ignores: ['.next/**', 'out/**', 'node_modules/**', 'next-env.d.ts'] },
  ...next,
];

export default config;
