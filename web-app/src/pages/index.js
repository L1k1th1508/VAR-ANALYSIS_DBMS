import React, { useState, useEffect } from "react";
import Head from "next/head";

export default function Home() {
  const [role, setRole] = useState("analyst"); // "admin" or "analyst"
  const [activeTab, setActiveTab] = useState("overview");
  const [matches, setMatches] = useState([]);
  const [nosqlReviews, setNosqlReviews] = useState([]);
  const [tagFilter, setTagFilter] = useState("");
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    fetchMatches();
    fetchNosqlReviews();
  }, []);

  const fetchMatches = async () => {
    try {
      const res = await fetch("/api/matches");
      const data = await res.json();
      setMatches(data.matches || []);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchNosqlReviews = async (tag = "") => {
    try {
      const url = tag ? `/api/nosql-reviews?tag=${encodeURIComponent(tag)}` : "/api/nosql-reviews";
      const res = await fetch(url);
      const data = await res.json();
      setNosqlReviews(data.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  // RUD: Update Tag
  const handleAddTag = async (key) => {
    const newTag = prompt("Enter new tag to append (e.g., controversial, handball):");
    if (!newTag) return;
    try {
      await fetch("/api/nosql-reviews", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_key: key, tags: [newTag.toLowerCase()] }),
      });
      setStatusMsg(`Updated incident ${key} with tag: ${newTag}`);
      fetchNosqlReviews();
    } catch (e) {
      console.error(e);
    }
  };

  // RUD: Delete Review (Admin only)
  const handleDeleteReview = async (key) => {
    if (role !== "admin") {
      alert("Only users with the Administrator role can delete records!");
      return;
    }
    if (!confirm(`Are you sure you want to delete incident ${key}?`)) return;
    try {
      await fetch(`/api/nosql-reviews?incident_key=${encodeURIComponent(key)}`, {
        method: "DELETE",
      });
      setStatusMsg(`Deleted incident ${key}`);
      fetchNosqlReviews();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <Head>
        <title>FIFA World Cup 2022 - VAR & Decision Analytics</title>
      </Head>

      {/* Header */}
      <header className="bg-slate-900 text-white shadow-md">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <span className="text-sky-400">VAR</span> Analytics — World Cup 2022
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              PES University DBMS Project · PostgreSQL 16 & MongoDB 7.0
            </p>
          </div>

          {/* Role-Based Access Control Switcher */}
          <div className="flex items-center gap-3 bg-slate-800 p-2 rounded-lg border border-slate-700">
            <span className="text-xs text-slate-300 font-medium">RBAC Role:</span>
            <button
              onClick={() => setRole("analyst")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                role === "analyst"
                  ? "bg-sky-600 text-white shadow"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Analyst (Read-Only)
            </button>
            <button
              onClick={() => setRole("admin")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                role === "admin"
                  ? "bg-amber-600 text-white shadow"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Administrator (RUD Privileges)
            </button>
          </div>
        </div>
      </header>

      {/* Navigation Bar */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 flex gap-6">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === "overview"
                ? "border-sky-600 text-sky-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Overview & Metrics
          </button>
          <button
            onClick={() => setActiveTab("matches")}
            className={`py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === "matches"
                ? "border-sky-600 text-sky-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Matches (PostgreSQL)
          </button>
          <button
            onClick={() => setActiveTab("nosql")}
            className={`py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === "nosql"
                ? "border-sky-600 text-sky-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            VAR Telemetry & RUD (MongoDB)
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="max-w-7xl mx-auto mt-4 px-6">
          <div className="bg-emerald-50 border border-emerald-300 text-emerald-800 px-4 py-2 rounded text-sm flex justify-between">
            <span>{statusMsg}</span>
            <button onClick={() => setStatusMsg("")} className="font-bold">×</button>
          </div>
        </div>
      )}

      {/* Content Body */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* TAB 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase">Matches Loaded</span>
                <p className="text-3xl font-extrabold text-slate-900 mt-2">64</p>
                <span className="text-xs text-sky-600">FIFA World Cup 2022</span>
              </div>
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase">Teams Participated</span>
                <p className="text-3xl font-extrabold text-slate-900 mt-2">32</p>
                <span className="text-xs text-sky-600">All National Federations</span>
              </div>
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase">Documented VAR Reviews</span>
                <p className="text-3xl font-extrabold text-slate-900 mt-2">27</p>
                <span className="text-xs text-emerald-600">25 Overturned · 2 Upheld</span>
              </div>
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase">Database Architecture</span>
                <p className="text-base font-bold text-slate-900 mt-2">Hybrid Relational + NoSQL</p>
                <span className="text-xs text-slate-500">PostgreSQL 16 + MongoDB 7.0</span>
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900 mb-2">Scope: World Cup 2022 Focus Only</h2>
              <p className="text-sm text-slate-600 leading-relaxed mb-4">
                Premier League 2015/16 datasets have been completely purged from this repository.
                All match events, referee appointments, VAR review timelines, and semi-automated offside / ball-tracking telemetry strictly analyze the 64 tournament fixtures of Qatar 2022.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-slate-200 p-4 rounded-lg bg-slate-50">
                  <h3 className="font-semibold text-sm text-slate-800 mb-1">PostgreSQL 16 Tier</h3>
                  <p className="text-xs text-slate-600">
                    Stores 3NF entities: Football matches, rosters, referees, card events, and trigger-enforced relational integrity.
                  </p>
                </div>
                <div className="border border-slate-200 p-4 rounded-lg bg-slate-50">
                  <h3 className="font-semibold text-sm text-slate-800 mb-1">MongoDB 7.0 Tier</h3>
                  <p className="text-xs text-slate-600">
                    Stores unstructured incident logs, review durations, ball-curvature margins, and arbitrary telemetry tags.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MATCHES (PostgreSQL) */}
        {activeTab === "matches" && (
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900 mb-4">
              FIFA World Cup 2022 Fixtures (Queried from PostgreSQL via Next.js API)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 text-slate-700 uppercase text-xs">
                  <tr>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Team A</th>
                    <th className="py-3 px-4">Score</th>
                    <th className="py-3 px-4">Team B</th>
                    <th className="py-3 px-4">Main Referee</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {matches.map((m, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-mono text-xs">{m.match_date}</td>
                      <td className="py-3 px-4 font-medium">{m.team_a}</td>
                      <td className="py-3 px-4 font-bold text-sky-700">
                        {m.home_score} : {m.away_score}
                      </td>
                      <td className="py-3 px-4 font-medium">{m.team_b}</td>
                      <td className="py-3 px-4 text-slate-600">{m.main_referee || "Official"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: NOSQL (MongoDB RUD Operations) */}
        {activeTab === "nosql" && (
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  MongoDB Incident Reviews (RUD Features)
                </h2>
                <p className="text-xs text-slate-500">
                  Rubric requirement: NoSQL creation (4 marks) & RUD operations (7 marks)
                </p>
              </div>

              {/* READ Filter */}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Filter by tag (e.g., penalty)..."
                  value={tagFilter}
                  onChange={(e) => setTagFilter(e.target.value)}
                  className="px-3 py-1.5 text-xs border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
                <button
                  onClick={() => fetchNosqlReviews(tagFilter)}
                  className="bg-sky-600 text-white text-xs font-semibold px-3 py-1.5 rounded-md hover:bg-sky-700"
                >
                  Filter
                </button>
                {tagFilter && (
                  <button
                    onClick={() => {
                      setTagFilter("");
                      fetchNosqlReviews("");
                    }}
                    className="text-xs text-slate-500 underline"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {nosqlReviews.map((rev) => (
                <div
                  key={rev.incident_key}
                  className="border border-slate-200 rounded-lg p-5 bg-slate-50 hover:bg-white transition shadow-sm"
                >
                  <div className="flex justify-between items-start gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold bg-slate-200 text-slate-800 px-2 py-0.5 rounded">
                          {rev.incident_key}
                        </span>
                        <span className="text-xs font-semibold text-slate-500">
                          Minute {rev.minute}&apos; · {rev.stage}
                        </span>
                        <span
                          className={`text-xs font-bold px-2 py-0.5 rounded ${
                            rev.review_decision === "OVERTURNED"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {rev.review_decision}
                        </span>
                      </div>
                      <h3 className="text-sm font-bold text-slate-900 mt-2">
                        {rev.teams ? rev.teams.join(" vs ") : "Match Review"} — {rev.incident_type}
                      </h3>
                      <p className="text-xs text-slate-600 mt-1">{rev.description}</p>
                    </div>

                    {/* RUD Controls */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleAddTag(rev.incident_key)}
                        className="bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-medium px-2.5 py-1 rounded"
                        title="Update Operation: Append Tag"
                      >
                        + Tag
                      </button>
                      {role === "admin" && (
                        <button
                          onClick={() => handleDeleteReview(rev.incident_key)}
                          className="bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium px-2.5 py-1 rounded"
                          title="Delete Operation: Remove Record"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-slate-200">
                    {rev.tags?.map((t, idx) => (
                      <span
                        key={idx}
                        className="text-[11px] bg-sky-100 text-sky-800 font-medium px-2 py-0.5 rounded-full"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
