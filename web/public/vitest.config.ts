import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

const directory = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  test: {
    environment: "jsdom",
    include: [`${directory}/tests/**/*.test.ts`],
    restoreMocks: true,
  },
});
