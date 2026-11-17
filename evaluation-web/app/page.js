"use client";
import { useEffect, useState } from "react";

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
function mutation(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
export default function Home() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [status, setStatus] = useState("");
  const [active, setActive] = useState(false),
    [notes, setNotes] = useState([]),
    [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  async function loadNotes() {
    setNotes(await api("/api/notes"));
  }
  useEffect(() => {
    api("/api/analytics")
      .then(setData)
      .catch((e) => setError(e.message));
    api("/api/session")
      .then(async (s) => {
        setActive(s.authenticated);
        if (s.authenticated) await loadNotes();
      })
      .catch((e) => setError(e.message));
  }, []);
  async function action(callback) {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await callback();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main>
      <header>
        <a className="brand" href="/">
          Referee & VAR
        </a>
        <a href="http://127.0.0.1:8501" target="_blank" rel="noreferrer">
          Open full dashboard ↗
        </a>
      </header>
      <section className="intro">
        <p className="eyebrow">Football decision analytics</p>
        <h1>
          Match decisions.
          <br />
          Source evidence.
        </h1>
        <p>
          Explore recorded decisions from PostgreSQL and keep cited research
          notes in MongoDB.
        </p>
      </section>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {status && (
        <p role="status" className="success">
          {status}
        </p>
      )}
      <section aria-label="Dataset totals" className="metrics">
        {data ? (
          Object.entries(data.totals).map(([k, v]) => (
            <article key={k}>
              <strong>{Number(v).toLocaleString()}</strong>
              <span>{k}</span>
            </article>
          ))
        ) : (
          <p>Loading analytics…</p>
        )}
      </section>
      <section className="panel">
        <h2>Match explorer</h2>
        <p>
          Up to 100 loaded fixtures, ordered by date. Full season and date filtering are
          available in the dashboard.
        </p>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Competition</th>
                <th>Home</th>
                <th>Score</th>
                <th>Away</th>
              </tr>
            </thead>
            <tbody>
              {data?.matches.map((m) => (
                <tr key={m.match_id}>
                  <td>{m.match_date?.slice(0, 10) || "Unknown"}</td>
                  <td>{m.league}</td>
                  <td>{m.home_team}</td>
                  <td>
                    {m.home_score ?? "–"} : {m.away_score ?? "–"}
                  </td>
                  <td>{m.away_team}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <h2>Research notebook</h2>
        <p>
          The latest 100 cited analyst annotations are stored as MongoDB
          documents. They are independent of verified match facts in PostgreSQL.
        </p>
        {!active ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = e.currentTarget;
              action(async () => {
                await api(
                  "/api/session",
                  mutation("POST", {
                    password: new FormData(f).get("password"),
                  }),
                );
                setActive(true);
                f.reset();
                await loadNotes();
              });
            }}
          >
            <label>
              Administrator password
              <input
                name="password"
                type="password"
                required
                autoComplete="current-password"
                maxLength={1024}
              />
            </label>
            <button disabled={busy}>Sign in</button>
          </form>
        ) : (
          <>
            <div className="toolbar">
              <button
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    await loadNotes();
                    setStatus("Notebook reloaded");
                  })
                }
              >
                Reload notes
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    await api("/api/session", { method: "DELETE" });
                    setActive(false);
                    setNotes([]);
                    setEditing(null);
                  })
                }
              >
                Sign out
              </button>
            </div>
            <form
              key={editing?._id || "new"}
              onSubmit={(e) => {
                e.preventDefault();
                const f = e.currentTarget;
                const fields = Object.fromEntries(new FormData(f));
                action(async () => {
                  await api(
                    "/api/notes",
                    mutation(editing ? "PUT" : "POST", {
                      ...fields,
                      ...(editing
                        ? { id: editing._id, revision: editing.revision }
                        : {}),
                    }),
                  );
                  setEditing(null);
                  f.reset();
                  await loadNotes();
                  setStatus("Note saved");
                });
              }}
            >
              <h3>{editing ? "Edit note" : "Add a cited note"}</h3>
              <label>
                Title
                <input
                  name="title"
                  defaultValue={editing?.title || ""}
                  required
                  maxLength={150}
                />
              </label>
              <label>
                Evidence URL
                <input
                  name="sourceUrl"
                  type="url"
                  pattern="https://.*"
                  placeholder="https://…"
                  defaultValue={editing?.sourceUrl || ""}
                  required
                />
              </label>
              <label>
                Observation
                <textarea
                  name="body"
                  rows={4}
                  maxLength={10000}
                  defaultValue={editing?.body || ""}
                  required
                />
              </label>
              <button disabled={busy}>Save note</button>
              {editing && (
                <button type="button" onClick={() => setEditing(null)}>
                  Cancel edit
                </button>
              )}
            </form>
            <div className="notes">
              {notes.length === 0 && <p>No research notes yet.</p>}
              {notes.map((n) => (
                <article key={n._id}>
                  <h3>{n.title}</h3>
                  <p className="note-body">{n.body}</p>
                  <a href={n.sourceUrl} target="_blank" rel="noreferrer">
                    View evidence ↗
                  </a>
                  <small>
                    Updated {new Date(n.updatedAt).toLocaleString()}
                  </small>
                  <div className="toolbar">
                    <button disabled={busy} onClick={() => setEditing(n)}>
                      Edit
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm(`Delete “${n.title}”?`))
                          action(async () => {
                            await api(
                              "/api/notes",
                              mutation("DELETE", {
                                id: n._id,
                                revision: n.revision,
                              }),
                            );
                            if (editing?._id === n._id) setEditing(null);
                            await loadNotes();
                            setStatus("Note deleted");
                          });
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
      <footer>
        Coverage is partial. Recorded events alone do not establish decision
        correctness or referee bias.
      </footer>
    </main>
  );
}
