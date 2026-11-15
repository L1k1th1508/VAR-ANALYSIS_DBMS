-- Reviewed awards/claims are distinct from the primary adapter's goals and penalty shots.
INSERT INTO var.decision_type(decision_type_code,label) VALUES
    ('GOAL_REVIEW','Reviewed goal decision'), ('PENALTY_REVIEW','Reviewed penalty claim');
