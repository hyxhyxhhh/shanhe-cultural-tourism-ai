import assert from "node:assert/strict";
import test from "node:test";
import { eventAgentLoginHref, resolveLoginReturnTo } from "./login-return.ts";

test("event agent login href carries the confirmed return destination", () => {
  assert.equal(eventAgentLoginHref(), "/login?returnTo=%2Fevent-agent");
});

test("login return destination accepts only the confirmed event agent route", () => {
  assert.equal(resolveLoginReturnTo("/event-agent"), "/event-agent");
  assert.equal(resolveLoginReturnTo("https://example.com"), "/cockpits");
  assert.equal(resolveLoginReturnTo("//example.com"), "/cockpits");
  assert.equal(resolveLoginReturnTo(["/event-agent"]), "/cockpits");
  assert.equal(resolveLoginReturnTo(undefined), "/cockpits");
});
