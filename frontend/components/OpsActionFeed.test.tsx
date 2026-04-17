// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import OpsActionFeed from "./OpsActionFeed";
import { ToastProvider } from "./Toast";

describe("OpsActionFeed", () => {
  it("renders the login-needed state when no token is supplied", () => {
    const html = renderToString(
      <ToastProvider>
        <OpsActionFeed token={null} />
      </ToastProvider>,
    );
    expect(html).toContain("Propose Actions");
    expect(html).toContain("disabled");
    expect(html).toMatchSnapshot();
  });

  it("enables Propose Actions when a token is present", () => {
    const html = renderToString(
      <ToastProvider>
        <OpsActionFeed token="jwt.fake.token" />
      </ToastProvider>,
    );
    // Button should be rendered without the disabled attribute for the
    // primary action (Propose Actions). React SSR emits `disabled=""` only
    // when disabled is true.
    const proposeBtn = html.match(/<button[^>]*>Propose Actions<\/button>/);
    expect(proposeBtn).toBeTruthy();
    expect(proposeBtn?.[0]).not.toContain("disabled");
  });
});
