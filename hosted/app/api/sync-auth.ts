import { getChatGPTUser } from "../chatgpt-auth";

type RuntimeEnv = {
  HANLU_SYNC_KEY?: string;
  HANLU_SYNC_USER_ID?: string;
};

export async function getProgressUser(request: Request) {
  const browserUser = await getChatGPTUser();
  if (browserUser) return { id: browserUser.id, machine: false };

  const supplied = request.headers.get("x-hanlu-sync-key") ?? "";
  const { env } = await import("cloudflare:workers");
  const runtime = env as unknown as RuntimeEnv;
  if (!runtime.HANLU_SYNC_KEY || !runtime.HANLU_SYNC_USER_ID ||
      !(await securelyEqual(supplied, runtime.HANLU_SYNC_KEY))) return null;
  return { id: runtime.HANLU_SYNC_USER_ID, machine: true };
}

async function securelyEqual(left: string, right: string) {
  const encoder = new TextEncoder();
  const [leftHash, rightHash] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(left)),
    crypto.subtle.digest("SHA-256", encoder.encode(right)),
  ]);
  const a = new Uint8Array(leftHash);
  const b = new Uint8Array(rightHash);
  let different = a.length ^ b.length;
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) different |= a[index] ^ b[index];
  return different === 0;
}
