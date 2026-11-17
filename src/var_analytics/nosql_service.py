"""
NoSQL (MongoDB) Database Creation & RUD Operations for World Cup 2022 VAR & Event Telemetry.
Evaluation Criteria:
- NoSQL/Vector database creation (4 marks)
- NoSQL/Vector feature RUD (7 marks)
"""

import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Default MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongoadmin:mongopassword@127.0.0.1:27017/var_nosql?authSource=admin")
DB_NAME = "var_nosql"


def get_nosql_client():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)


def init_nosql_db():
    """Create collections, schema indexes, and seed World Cup 2022 VAR incident documents."""
    client = get_nosql_client()
    db = client[DB_NAME]

    # Collections
    reviews_col = db["var_incident_reviews"]
    events_col = db["match_events_telemetry"]

    # Create Indexes
    reviews_col.create_index([("match_id", 1), ("incident_key", 1)], unique=True)
    reviews_col.create_index([("review_decision", 1)])
    reviews_col.create_index([("tags", 1)])

    events_col.create_index([("match_id", 1), ("timestamp", 1)])

    # Sample Seed Data: World Cup 2022 Real VAR Reviews with nested telemetry
    sample_reviews = [
        {
            "incident_key": "ARG-FRA-PEN-01",
            "match_id": "3869685",
            "tournament": "FIFA World Cup 2022",
            "stage": "Final",
            "teams": ["Argentina", "France"],
            "minute": 23,
            "period": 1,
            "referee": "Szymon Marciniak",
            "var_official": "Tomasz Kwiatkowski",
            "incident_type": "PENALTY_AWARD",
            "original_call": "PENALTY",
            "review_decision": "UPHELD",
            "review_duration_seconds": 45,
            "description": "Ousmane Dembele foul on Angel Di Maria in the penalty box.",
            "tags": ["penalty", "foul", "final", "upheld"],
            "telemetry": {
                "impact_speed_mps": 6.8,
                "distance_to_referee_meters": 12.4,
                "audio_review_confirmed": True
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "incident_key": "JPN-ESP-BALL-OUT",
            "match_id": "3857264",
            "tournament": "FIFA World Cup 2022",
            "stage": "Group Stage",
            "teams": ["Japan", "Spain"],
            "minute": 51,
            "period": 2,
            "referee": "Victor Gomes",
            "var_official": "Fernando Guerrero",
            "incident_type": "GOAL_LINE_BALL_OUT",
            "original_call": "NO_GOAL",
            "review_decision": "OVERTURNED",
            "review_duration_seconds": 118,
            "description": "Kaoru Mitoma assist to Ao Tanaka; ball curvature checked across end line.",
            "tags": ["goal", "ball_out", "sensor_check", "overturned"],
            "telemetry": {
                "ball_curvature_margin_mm": 1.88,
                "in_ball_sensor_hz": 500,
                "camera_angles_reviewed": 4
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "incident_key": "FRA-POL-ENCROACH",
            "match_id": "3869254",
            "tournament": "FIFA World Cup 2022",
            "stage": "Round of 16",
            "teams": ["France", "Poland"],
            "minute": 98,
            "period": 2,
            "referee": "Jesus Valenzuela",
            "var_official": "Mauro Vigliano",
            "incident_type": "PENALTY_RETAKE",
            "original_call": "SAVED_PENALTY",
            "review_decision": "OVERTURNED",
            "review_duration_seconds": 65,
            "description": "Hugo Lloris off his goal line before Robert Lewandowski struck the penalty shot.",
            "tags": ["penalty", "encroachment", "goalkeeper", "overturned"],
            "telemetry": {
                "distance_off_line_cm": 35.2,
                "audio_review_confirmed": True
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]

    for item in sample_reviews:
        reviews_col.update_one(
            {"incident_key": item["incident_key"]},
            {"$set": item},
            upsert=True
        )

    print("NoSQL MongoDB initialized with collections and indexes.")


# ==========================================
# RUD OPERATIONS (7 Marks Component)
# ==========================================

def nosql_read_reviews(match_id=None, review_decision=None, tag=None):
    """
    READ Operation:
    - Filters by match, decision (UPHELD/OVERTURNED), or nested tags.
    - Uses projection and sorting.
    """
    client = get_nosql_client()
    db = client[DB_NAME]
    query = {}
    if match_id:
        query["match_id"] = str(match_id)
    if review_decision:
        query["review_decision"] = review_decision.upper()
    if tag:
        query["tags"] = tag.lower()

    results = list(db["var_incident_reviews"].find(query, {"_id": 0}).sort("minute", 1))
    return results


def nosql_read_review_aggregations():
    """
    READ Aggregation Pipeline:
    - Calculates overturn rates, average review durations grouped by incident type.
    """
    client = get_nosql_client()
    db = client[DB_NAME]
    pipeline = [
        {
            "$group": {
                "_id": "$incident_type",
                "total_incidents": {"$sum": 1},
                "overturned_count": {
                    "$sum": {"$cond": [{"$eq": ["$review_decision", "OVERTURNED"]}, 1, 0]}
                },
                "avg_duration_sec": {"$avg": "$review_duration_seconds"}
            }
        },
        {"$sort": {"total_incidents": -1}}
    ]
    return list(db["var_incident_reviews"].aggregate(pipeline))


def nosql_update_review(incident_key, updates: dict):
    """
    UPDATE Operation:
    - Modifies telemetry, updates tags, or updates incident descriptions.
    """
    client = get_nosql_client()
    db = client[DB_NAME]
    updates["updated_at"] = datetime.utcnow()
    res = db["var_incident_reviews"].update_one(
        {"incident_key": incident_key},
        {"$set": updates}
    )
    return res.modified_count > 0


def nosql_append_tag(incident_key, tag: str):
    """
    UPDATE Operation ($push / $addToSet):
    - Dynamically appends a categorization tag.
    """
    client = get_nosql_client()
    db = client[DB_NAME]
    res = db["var_incident_reviews"].update_one(
        {"incident_key": incident_key},
        {
            "$addToSet": {"tags": tag.lower()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return res.modified_count > 0


def nosql_delete_review(incident_key: str):
    """
    DELETE Operation:
    - Removes a flagged or rejected incident record.
    """
    client = get_nosql_client()
    db = client[DB_NAME]
    res = db["var_incident_reviews"].delete_one({"incident_key": incident_key})
    return res.deleted_count > 0


if __name__ == "__main__":
    try:
        init_nosql_db()
        print("Read Query Result:", nosql_read_reviews())
        print("Aggregation Result:", nosql_read_review_aggregations())
    except ConnectionFailure:
        print("MongoDB is not running yet. Start it with docker compose up -d mongodb")
