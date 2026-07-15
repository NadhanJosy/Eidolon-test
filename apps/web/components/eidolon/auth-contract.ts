import type { AuthResponse, User } from "./types";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const OFFSET_TIMESTAMP_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/;
const EMAIL_LOCAL_PATTERN = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+$/;
const EMAIL_DOMAIN_LABEL_PATTERN =
  /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
const JWT_PATTERN = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
const CONTROL_OR_FORMAT_PATTERN = /[\p{Cc}\p{Cf}]/u;
const MAX_EMAIL_LENGTH = 320;
const MAX_EMAIL_LOCAL_LENGTH = 64;
const MAX_EMAIL_DOMAIN_LENGTH = 253;
const MAX_DISPLAY_NAME_LENGTH = 120;
const MAX_ACCESS_TOKEN_LENGTH = 4096;

export type AuthResponseExpectation = {
  email?: string;
  userId?: string;
};

export function canonicalAuthEmail(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (
    normalized.length === 0 ||
    normalized.length > MAX_EMAIL_LENGTH ||
    countCharacter(normalized, "@") !== 1
  ) {
    return null;
  }

  const [localPart, domain] = normalized.split("@");
  if (
    !localPart ||
    localPart.length > MAX_EMAIL_LOCAL_LENGTH ||
    localPart.startsWith(".") ||
    localPart.endsWith(".") ||
    localPart.includes("..") ||
    !EMAIL_LOCAL_PATTERN.test(localPart) ||
    !domain ||
    domain.length > MAX_EMAIL_DOMAIN_LENGTH
  ) {
    return null;
  }

  const labels = domain.split(".");
  if (
    labels.length < 2 ||
    labels.some((label) => !EMAIL_DOMAIN_LABEL_PATTERN.test(label))
  ) {
    return null;
  }
  return normalized;
}

export function canonicalDisplayName(value: string): string | null | undefined {
  if (value.length > MAX_DISPLAY_NAME_LENGTH || CONTROL_OR_FORMAT_PATTERN.test(value)) {
    return undefined;
  }
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized || null;
}

export function ownedUser(
  value: unknown,
  expectation: AuthResponseExpectation = {}
): User | null {
  if (!plainObject(value)) {
    return null;
  }
  const email = typeof value.email === "string" ? canonicalAuthEmail(value.email) : null;
  const displayName = validDisplayName(value.display_name);
  if (
    !validUuid(value.id) ||
    !email ||
    displayName === undefined ||
    typeof value.age_gate_confirmed !== "boolean" ||
    !validTimestamp(value.created_at) ||
    (expectation.userId !== undefined && value.id !== expectation.userId) ||
    (expectation.email !== undefined && email !== expectation.email)
  ) {
    return null;
  }
  return {
    id: value.id,
    email,
    display_name: displayName,
    age_gate_confirmed: value.age_gate_confirmed,
    created_at: value.created_at
  };
}

export function completeAuthResponse(
  value: unknown,
  expectation: AuthResponseExpectation = {}
): AuthResponse | null {
  if (!plainObject(value)) {
    return null;
  }
  const user = ownedUser(value.user, expectation);
  if (
    !user ||
    typeof value.access_token !== "string" ||
    value.access_token.length === 0 ||
    value.access_token.length > MAX_ACCESS_TOKEN_LENGTH ||
    !JWT_PATTERN.test(value.access_token) ||
    !accessTokenMatchesUser(value.access_token, user.id) ||
    value.token_type !== "bearer"
  ) {
    return null;
  }
  return {
    access_token: value.access_token,
    token_type: "bearer",
    user
  };
}

function accessTokenMatchesUser(token: string, userId: string): boolean {
  const [encodedHeader, encodedPayload] = token.split(".");
  const header = decodeJwtSegment(encodedHeader);
  const payload = decodeJwtSegment(encodedPayload);
  if (!plainObject(header) || !plainObject(payload)) {
    return false;
  }
  const issuedAt = finiteInteger(payload.iat);
  const notBefore = finiteInteger(payload.nbf);
  const expiresAt = finiteInteger(payload.exp);
  return (
    header.alg === "HS256" &&
    header.typ === "JWT" &&
    payload.sub === userId &&
    payload.iss === "eidolon-api" &&
    payload.aud === "eidolon-web" &&
    payload.type === "access" &&
    validUuid(payload.jti) &&
    issuedAt !== null &&
    notBefore !== null &&
    expiresAt !== null &&
    issuedAt <= notBefore &&
    notBefore < expiresAt
  );
}

function decodeJwtSegment(value: string | undefined): unknown {
  if (!value) {
    return null;
  }
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  try {
    return JSON.parse(globalThis.atob(`${normalized}${padding}`));
  } catch {
    return null;
  }
}

function finiteInteger(value: unknown): number | null {
  return Number.isSafeInteger(value) ? (value as number) : null;
}

function validDisplayName(value: unknown): string | null | undefined {
  if (value === null) {
    return null;
  }
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = canonicalDisplayName(value);
  return normalized === value ? value : undefined;
}

function validTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || !OFFSET_TIMESTAMP_PATTERN.test(value)) {
    return false;
  }
  return Number.isFinite(Date.parse(value));
}

function validUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function plainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function countCharacter(value: string, character: string): number {
  let count = 0;
  for (const candidate of value) {
    if (candidate === character) {
      count += 1;
    }
  }
  return count;
}
