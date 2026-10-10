const DEFAULT_LOGIN_DESTINATION = "/cockpits";
const EVENT_AGENT_DESTINATION = "/event-agent";

export function eventAgentLoginHref() {
  return `/login?returnTo=${encodeURIComponent(EVENT_AGENT_DESTINATION)}`;
}

export function resolveLoginReturnTo(value: unknown) {
  return value === EVENT_AGENT_DESTINATION ? EVENT_AGENT_DESTINATION : DEFAULT_LOGIN_DESTINATION;
}
