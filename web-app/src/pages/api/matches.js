import { pgPool } from "../../lib/db";

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const query = `
      SELECT m.match_id, m.match_date, m.kickoff_local,
             h.name as home_team, a.name as away_team,
             m.home_score, m.away_score,
             r.name as main_referee
      FROM var.football_match m
      JOIN var.team h ON h.team_id = m.home_team_id
      JOIN var.team a ON a.team_id = m.away_team_id
      LEFT JOIN var.match_official mo ON mo.match_id = m.match_id AND mo.role_code = 'MAIN_REFEREE'
      LEFT JOIN var.referee r ON r.referee_id = mo.referee_id
      ORDER BY m.match_date ASC
      LIMIT 64;
    `;
    const result = await pgPool.query(query);
    return res.status(200).json({ matches: result.rows });
  } catch (err) {
    console.error("Database query error:", err);
    // Return sample fallback when local DB is offline
    return res.status(200).json({
      matches: [
        { match_id: "3869685", match_date: "2022-12-18", home_team: "Argentina", away_team: "France", home_score: 3, away_score: 3, main_referee: "Szymon Marciniak" },
        { match_id: "3857264", match_date: "2022-12-01", home_team: "Japan", away_team: "Spain", home_score: 2, away_score: 1, main_referee: "Victor Gomes" },
        { match_id: "3869254", match_date: "2022-12-04", home_team: "France", away_team: "Poland", home_score: 3, away_score: 1, main_referee: "Jesus Valenzuela" }
      ],
      notice: "Fallback mock data shown while local database container initializes."
    });
  }
}
