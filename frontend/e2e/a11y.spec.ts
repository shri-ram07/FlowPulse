import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/**
 * Automated accessibility scan on every public page.
 *
 * Uses axe-core (WCAG 2.1 A/AA rules) via Playwright. We gate on
 * `critical` and `serious` violations — these correspond to real
 * user-blocking issues. `moderate` / `minor` rules are logged but
 * don't fail the build, since some are legitimately false-positive
 * on Next.js SSR markup (inline styles etc.).
 */

const BLOCKING = ["critical", "serious"] as const;

async function scanAndAssert(page: import("@playwright/test").Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .disableRules(["color-contrast"]) // checked separately via Lighthouse
    .analyze();

  const blocking = results.violations.filter((v) =>
    (BLOCKING as readonly string[]).includes(v.impact ?? "minor"),
  );
  if (blocking.length) {
    console.log(
      `\n[a11y] ${label} blocking violations:\n` +
        blocking.map((v) => `  - ${v.id} (${v.impact}): ${v.help}`).join("\n"),
    );
  }
  expect.soft(blocking, `axe violations on ${label}`).toEqual([]);
}

test("welcome page is accessible", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Welcome to FlowPulse/ })).toBeVisible();
  await scanAndAssert(page, "/");
});

test("live map is accessible", async ({ page }) => {
  await page.goto("/map");
  await expect(page.getByRole("heading", { name: /Live Stadium Map/ })).toBeVisible();
  await scanAndAssert(page, "/map");
});

test("concierge chat page is accessible", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: /Pick your location/ })).toBeVisible();
  await scanAndAssert(page, "/chat");
});

test("ops login page is accessible", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.getByRole("heading", { name: /Staff sign in/ })).toBeVisible();
  await scanAndAssert(page, "/ops");
});

test("skip link is first focusable element", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /Skip to main content/ })).toBeFocused();
});
