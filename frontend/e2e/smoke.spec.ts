import { expect, test } from "@playwright/test";

/**
 * Smoke test: exercises the three main routes and asserts the most
 * distinctive landmarks on each. Does NOT assume the backend is up —
 * the welcome page is static and the ops/chat pages render their shell
 * before the WebSocket connects.
 */

test("welcome page renders hero + how-it-works", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Welcome to FlowPulse/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open Live Map/ })).toBeVisible();
  await expect(page.getByText(/How FlowPulse actually reduces congestion/)).toBeVisible();
});

test("map page renders map panel and hotspot section", async ({ page }) => {
  await page.goto("/map");
  await expect(page.getByRole("heading", { name: /Live Stadium Map/ })).toBeVisible();
});

test("ops page requires login", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.getByRole("heading", { name: /Staff sign in/ })).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
});

test("skip link is focusable for keyboard users", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: /Skip to main content/ });
  await expect(skip).toBeFocused();
});
