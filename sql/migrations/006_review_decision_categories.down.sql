-- Foreign keys deliberately prevent removing vocabulary while evidence uses it.
DELETE FROM var.decision_type WHERE decision_type_code IN ('GOAL_REVIEW','PENALTY_REVIEW');
