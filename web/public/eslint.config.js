import js from "@eslint/js";
import lit from "eslint-plugin-lit";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**"] },
  {
    ...js.configs.recommended,
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.ts"],
    plugins: { lit },
    rules: {
      ...lit.configs.recommended.rules,
    },
  },
);
