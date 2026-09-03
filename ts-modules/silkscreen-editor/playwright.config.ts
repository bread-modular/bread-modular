import { defineConfig } from "@playwright/test";
import { fixtureServerEnv, FIXTURE_ENTRY } from "./e2e/fixture";

const serverEnv = fixtureServerEnv();

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  retries: 0,
  workers: 1, // saves mutate the fixture file — never parallelize
  use: {
    baseURL: "http://localhost:5175",
  },
  // The dev server boots itself per suite run against the disposable drive
  // fixture (SILK_ENTRY) — no manual `./silk.sh dev` needed. reuseExisting
  // Server keeps local iteration fast (`./silk.sh dev <fixture>` by hand,
  // then tests attach to it).
  webServer: {
    command: "../node_modules/.bin/bun run dev --port 5175 --strictPort",
    url: "http://localhost:5175/api/entry",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      ...serverEnv,
      SILK_ENTRY: FIXTURE_ENTRY,
    },
  },
});
