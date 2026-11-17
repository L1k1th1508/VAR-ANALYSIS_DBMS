import { NextResponse } from "next/server";
import {
  authorized,
  bridge,
  sameOrigin,
  sessionToken,
} from "../../../lib/server";
export async function GET(request) {
  return NextResponse.json({ authenticated: authorized(request) });
}
export async function POST(request) {
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Origin rejected" }, { status: 403 });
  try {
    const { password } = await request.json();
    if (typeof password !== "string" || password.length > 1024)
      return NextResponse.json({ error: "Invalid password" }, { status: 400 });
    const result = await bridge({ action: "authenticate", password });
    if (!result.authenticated)
      return NextResponse.json(
        { error: "Password was not accepted" },
        { status: 401 },
      );
    const response = NextResponse.json({ authenticated: true });
    response.cookies.set("var_session", sessionToken(), {
      httpOnly: true,
      sameSite: "strict",
      secure: new URL(request.url).protocol === "https:",
      path: "/",
      maxAge: 1800,
    });
    return response;
  } catch {
    return NextResponse.json({ error: "Sign-in unavailable" }, { status: 503 });
  }
}
export async function DELETE(request) {
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Origin rejected" }, { status: 403 });
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set("var_session", "", { path: "/", maxAge: 0 });
  return response;
}
