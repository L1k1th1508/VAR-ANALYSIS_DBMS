import { NextResponse } from "next/server";
import { bridge } from "../../../lib/server";
export const dynamic = "force-dynamic";
export async function GET(request) {
  const league = request.nextUrl.searchParams.get("league_id");
  try {
    return NextResponse.json(
      await bridge({ scope: league ? { league_id: league } : {} }),
    );
  } catch {
    return NextResponse.json(
      {
        error:
          "Analytics unavailable. Check PostgreSQL and server configuration.",
      },
      { status: 503 },
    );
  }
}
