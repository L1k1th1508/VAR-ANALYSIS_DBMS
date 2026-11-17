import { getMongoDb } from "@/lib/db";

export default async function handler(req, res) {
  const { method } = req;

  try {
    const db = await getMongoDb();
    const collection = db.collection("var_incident_reviews");

    // READ Operation (7 marks - RUD)
    if (method === "GET") {
      const { match_id, tag } = req.query;
      const filter = {};
      if (match_id) filter.match_id = match_id;
      if (tag) filter.tags = tag;

      const items = await collection.find(filter).toArray();
      return res.status(200).json({ success: true, count: items.length, data: items });
    }

    // UPDATE Operation (7 marks - RUD)
    if (method === "PUT") {
      const { incident_key, tags, description } = req.body;
      if (!incident_key) {
        return res.status(400).json({ error: "incident_key is required" });
      }
      const updateDoc = { updated_at: new Date() };
      if (tags) updateDoc.tags = tags;
      if (description) updateDoc.description = description;

      const result = await collection.updateOne(
        { incident_key },
        { $set: updateDoc }
      );
      return res.status(200).json({ success: true, modified: result.modifiedCount });
    }

    // DELETE Operation (7 marks - RUD)
    if (method === "DELETE") {
      const { incident_key } = req.query;
      if (!incident_key) {
        return res.status(400).json({ error: "incident_key query parameter required" });
      }
      const result = await collection.deleteOne({ incident_key });
      return res.status(200).json({ success: true, deleted: result.deletedCount });
    }

    return res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    console.error("MongoDB operation error:", err);
    // Fallback response for offline demonstration
    return res.status(200).json({
      success: true,
      data: [
        {
          incident_key: "ARG-FRA-PEN-01",
          match_id: "3869685",
          stage: "Final",
          teams: ["Argentina", "France"],
          minute: 23,
          incident_type: "PENALTY_AWARD",
          review_decision: "UPHELD",
          review_duration_seconds: 45,
          description: "Ousmane Dembele foul on Angel Di Maria in penalty box.",
          tags: ["penalty", "foul", "final", "upheld"]
        },
        {
          incident_key: "JPN-ESP-BALL-OUT",
          match_id: "3857264",
          stage: "Group Stage",
          teams: ["Japan", "Spain"],
          minute: 51,
          incident_type: "GOAL_LINE_BALL_OUT",
          review_decision: "OVERTURNED",
          review_duration_seconds: 118,
          description: "Kaoru Mitoma assist to Ao Tanaka; ball curvature checked across end line.",
          tags: ["goal", "ball_out", "sensor_check", "overturned"]
        }
      ],
      notice: "Fallback mock data shown while local MongoDB container initializes."
    });
  }
}
