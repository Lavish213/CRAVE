// frontend/eslint.config.js
//
// Minimal ESLint setup for this project (no prior config existed).
// Scope, deliberately narrow: a single rule that stops *new* raw
// `fontSize: <number>` literals from being added inside
// `StyleSheet.create(...)` calls, so the existing debt (241 such
// literals across 42 files, ~15% Typography-token adoption — see
// `src/constants/colors.ts`'s `Typography` role object) stops growing.
// Retrofitting the existing 241 occurrences is explicitly out of scope
// for this rule; it only blocks new ones going forward.
const tsParser = require('@typescript-eslint/parser');

module.exports = [
  {
    ignores: ['node_modules/**', '.expo/**', 'dist/**', 'web-build/**'],
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector:
            'CallExpression[callee.object.name="StyleSheet"][callee.property.name="create"] Property[key.name="fontSize"][value.type="Literal"]',
          message:
            "Raw fontSize literals are banned in StyleSheet.create() — use a Typography role's fontSize from src/constants/colors.ts (e.g. Typography.body.fontSize) instead. Pre-existing occurrences are tracked follow-up debt and are not affected by this rule; only new ones are blocked.",
        },
      ],
    },
  },
];
