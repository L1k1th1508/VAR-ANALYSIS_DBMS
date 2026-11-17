import { NextResponse } from "next/server";
import { ObjectId } from "mongodb";
import { authorized, notesCollection, sameOrigin } from "../../../lib/server";
function deny(request, mutation = false) {
  if (!authorized(request))
    return NextResponse.json(
      { error: "Administrator sign-in required" },
      { status: 401 },
    );
  if (mutation && !sameOrigin(request))
    return NextResponse.json({ error: "Origin rejected" }, { status: 403 });
}
function fields(value) {
  if (
    typeof value.title !== "string" ||
    !value.title.trim() ||
    value.title.length > 150
  )
    throw new Error("Title must contain 1–150 characters");
  if (
    typeof value.body !== "string" ||
    !value.body.trim() ||
    value.body.length > 10000
  )
    throw new Error("Note must contain 1–10,000 characters");
  const url = new URL(value.sourceUrl);
  if (url.protocol !== "https:") throw new Error("Evidence URL must use HTTPS");
  return {
    title: value.title.trim(),
    body: value.body.trim(),
    sourceUrl: url.href,
    updatedAt: new Date(),
  };
}
export async function GET(request) {
  const error = deny(request);
  if (error) return error;
  try {
    const collection = await notesCollection();
    const rows = await collection
      .find({})
      .sort({ updatedAt: -1 })
      .limit(100)
      .toArray();
    return NextResponse.json(rows);
  } catch {
    return NextResponse.json(
      { error: "Research notebook unavailable" },
      { status: 503 },
    );
  }
}
export async function POST(request) {
  const error = deny(request, true);
  if (error) return error;
  let value;
  try {
    value = fields(await request.json());
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 400 });
  }
  try {
    const collection = await notesCollection();
    const result = await collection.insertOne({
      ...value,
      createdAt: new Date(),
      revision: 1,
    });
    return NextResponse.json({ id: result.insertedId }, { status: 201 });
  } catch {
    return NextResponse.json(
      { error: "Note could not be saved" },
      { status: 503 },
    );
  }
}
export async function PUT(request) {
  const error = deny(request, true);
  if (error) return error;
  let value, id, version;
  try {
    const input = await request.json();
    value = fields(input);
    if (
      !ObjectId.isValid(input.id) ||
      (!Number.isSafeInteger(input.revision) || input.revision < 1)
    )
      throw new Error("Valid record ID and version required");
    id = new ObjectId(input.id);
    version = input.revision;
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 400 });
  }
  try {
    const collection = await notesCollection();
    const result = await collection.updateOne(
      { _id: id, revision: version },
      { $set: value, $inc: { revision: 1 } },
    );
    if (!result.matchedCount)
      return NextResponse.json(
        { error: "Note changed or was removed. Reload before editing." },
        { status: 409 },
      );
    return NextResponse.json({ saved: true });
  } catch {
    return NextResponse.json(
      { error: "Note could not be updated" },
      { status: 503 },
    );
  }
}
export async function DELETE(request) {
  const error = deny(request, true);
  if (error) return error;
  let input;
  try {
    input = await request.json();
    if (
      !ObjectId.isValid(input.id) ||
      (!Number.isSafeInteger(input.revision) || input.revision < 1)
    )
      throw new Error("Valid record ID and version required");
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 400 });
  }
  try {
    const collection = await notesCollection();
    const result = await collection.deleteOne({
      _id: new ObjectId(input.id),
      revision: input.revision,
    });
    if (!result.deletedCount)
      return NextResponse.json(
        { error: "Note changed or was removed. Reload before deleting." },
        { status: 409 },
      );
    return NextResponse.json({ deleted: true });
  } catch {
    return NextResponse.json(
      { error: "Note could not be deleted" },
      { status: 503 },
    );
  }
}
