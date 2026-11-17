import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHmac, timingSafeEqual } from "node:crypto";
import { MongoClient } from "mongodb";

const exec = promisify(execFile);
// The password hash is a private, high-entropy server secret shared by route bundles.
function signingKey() {
  const key = process.env.ADMIN_PASSWORD_HASH;
  if (!key) throw new Error("Administrator authentication is not configured");
  return key;
}
export async function bridge(request) {
  const child = exec(
    process.env.PORTAL_PYTHON || "python",
    ["-m", "var_analytics.portal_bridge"],
    { timeout: 20000, maxBuffer: 4 * 1024 * 1024 },
  );
  child.child.stdin.end(JSON.stringify(request));
  const { stdout } = await child;
  return JSON.parse(stdout);
}
function signature(body) {
  return createHmac("sha256", signingKey()).update(body).digest("hex");
}
export function sessionToken() {
  const body = Buffer.from(
    JSON.stringify({ expires: Date.now() + 1800000 }),
  ).toString("base64url");
  return body + "." + signature(body);
}
export function authorized(request) {
  const token = request.cookies.get("var_session")?.value || "";
  const [body, sig] = token.split(".");
  if (!body || !sig || !/^[a-f0-9]{64}$/.test(sig)) return false;
  const expected = Buffer.from(signature(body));
  if (!timingSafeEqual(expected, Buffer.from(sig))) return false;
  try {
    return (
      JSON.parse(Buffer.from(body, "base64url").toString()).expires > Date.now()
    );
  } catch {
    return false;
  }
}
let client;
export async function notesCollection() {
  if (!process.env.MONGO_URL) throw new Error("MongoDB is not configured");
  client ||= new MongoClient(process.env.MONGO_URL, {
    serverSelectionTimeoutMS: 5000,
  });
  await client.connect();
  return client.db("var_research").collection("notes");
}
export function sameOrigin(request) {
  try {
    const origin = new URL(request.headers.get("origin"));
    return ["http:", "https:"].includes(origin.protocol) && origin.host === request.headers.get("host");
  } catch {
    return false;
  }
}
