# src/graph/seed.py
from neo4j import GraphDatabase
from datetime import datetime, timedelta
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test1234")


def _run(tx, cypher, params=None):
    return tx.run(cypher, params or {})


def build_seed_graph():
    now = datetime.utcnow()
    now_iso = now.isoformat()
    tomorrow_iso = (now + timedelta(days=1)).isoformat()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as s:

        # ---------------------------
        # Constraints
        # ---------------------------
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Student) REQUIRE s.student_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Mentor) REQUIRE m.mentor_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (g:Goal) REQUIRE g.goal_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Assignment) REQUIRE a.assignment_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Conversation) REQUIRE c.conversation_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Intent) REQUIRE i.intent_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Decision) REQUIRE d.decision_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Screen) REQUIRE s.screen_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (dl:Deadline) REQUIRE dl.deadline_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cr:Course) REQUIRE cr.course_id IS UNIQUE",
        ]

        for query in constraints:
            s.execute_write(_run, query)

        # ---------------------------
        # Nodes
        # ---------------------------

        # Student
        s.execute_write(_run, """
        MERGE (st:Student {student_id: $sid})
        SET st.name = $name, st.email = $email
        """, {
            "sid": "s1", "name": "Rahul", "email": "rahul@example.com"
        })

        # Mentor
        s.execute_write(_run, """
        MERGE (m:Mentor {mentor_id: $mid})
        SET m.name = $name, m.email = $email
        """, {
            "mid": "m1", "name": "Dr. Sharma", "email": "mentor@example.com"
        })

        # Screen
        s.execute_write(_run, """
        MERGE (sc:Screen {screen_id: $sid})
        SET sc.name = $name
        """, {"sid": "screen1", "name": "assignment_page"})

        # Course
        s.execute_write(_run, """
        MERGE (cr:Course {course_id:$cid})
        SET cr.title = $title
        """, {"cid": "cr1", "title": "Complete Algebra Course"})

        # Goal
        s.execute_write(_run, """
        MERGE (g:Goal {goal_id:$gid})
        SET g.title = $title, g.status = $status, g.progress_percent = $progress
        """, {"gid": "g1", "title": "Complete Algebra Course", "status": "in_progress", "progress": 60})

        # Assignment
        s.execute_write(_run, """
        MERGE (a:Assignment {assignment_id:$aid})
        SET a.title = $title, a.status = $status
        """, {"aid": "a1", "title": "Linear Equations Worksheet", "status": "pending"})

        # Deadline
        s.execute_write(_run, """
        MERGE (dl:Deadline {deadline_id:$did})
        SET dl.due_at = $due_at, dl.type = $type
        """, {"did": "d1", "due_at": now_iso, "type": "hard"})

        # Decision
        s.execute_write(_run, """
        MERGE (dec:Decision {decision_id:$did})
        SET dec.decision_type = $type,
            dec.status = $status,
            dec.valid_until = $valid_until
        """, {
            "did": "dec1",
            "type": "extension",
            "status": "approved",
            "valid_until": tomorrow_iso
        })

        # Conversation
        s.execute_write(_run, """
        MERGE (c:Conversation {conversation_id:$cid})
        SET c.started_at = $started_at, c.last_message = $msg
        """, {"cid": "c1", "started_at": now_iso, "msg": "Can I get more time?"})

        # Intent
        s.execute_write(_run, """
        MERGE (i:Intent {intent_id:$iid})
        SET i.label = $label, i.confidence = $conf
        """, {"iid": "i1", "label": "deadline_help", "conf": 0.92})
        # ---------------------------
        # Relationships
        # ---------------------------

        # Student relationships
        s.execute_write(_run,
            "MATCH (st:Student {student_id:$sid}), (sc:Screen {screen_id:$scr}) "
            "MERGE (st)-[:CURRENT_SCREEN]->(sc)",
            {"sid": "s1", "scr": "screen1"}
        )

        s.execute_write(_run,
            "MATCH (st:Student {student_id:$sid}), (g:Goal {goal_id:$gid}) "
            "MERGE (st)-[:HAS_GOAL]->(g)",
            {"sid": "s1", "gid": "g1"}
        )

        s.execute_write(_run,
            "MATCH (st:Student {student_id:$sid}), (cr:Course {course_id:$cid}) "
            "MERGE (st)-[:ENROLLED_IN]->(cr)",
            {"sid": "s1", "cid": "cr1"}
        )

        s.execute_write(_run,
            "MATCH (st:Student {student_id:$sid}), (c:Conversation {conversation_id:$cid}) "
            "MERGE (st)-[:HAS_CONVERSATION]->(c)",
            {"sid": "s1", "cid": "c1"}
        )

        # Conversation -> Intent
        s.execute_write(_run,
            "MATCH (c:Conversation {conversation_id:$cid}), (i:Intent {intent_id:$iid})  "
            "MERGE (c)-[:INFERRED_INTENT]->(i)",
            {"cid": "c1", "iid": "i1"}
        )

        # Goal / Course structure
        s.execute_write(_run,
            "MATCH (g:Goal {goal_id:$gid}), (a:Assignment {assignment_id:$aid}) "
            "MERGE (g)-[:REQUIRES]->(a)",
            {"gid": "g1", "aid": "a1"}
        )

        s.execute_write(_run,
            "MATCH (cr:Course {course_id:$cid}), (a:Assignment {assignment_id:$aid}) "
            "MERGE (cr)-[:HAS_ASSIGNMENT]->(a)",
            {"cid": "cr1", "aid": "a1"}
        )

        s.execute_write(_run,
            "MATCH (a:Assignment {assignment_id:$aid}), (dl:Deadline {deadline_id:$did}) "
            "MERGE (a)-[:HAS_DEADLINE]->(dl)",
            {"aid": "a1", "did": "d1"}
        )

        # Decision modeling (NEW STRUCTURE)

        # Student HAS_DECISION
        s.execute_write(_run,
            "MATCH (st:Student {student_id:$sid}), (dec:Decision {decision_id:$did}) "
            "MERGE (st)-[:HAS_DECISION]->(dec)",
            {"sid": "s1", "did": "dec1"}
        )

        # Decision ABOUT assignment
        s.execute_write(_run,
            "MATCH (dec:Decision {decision_id:$did}), (a:Assignment {assignment_id:$aid}) "
            "MERGE (dec)-[:ABOUT]->(a)",
            {"did": "dec1", "aid": "a1"}
        )

        # Decision TAKEN_BY mentor
        s.execute_write(_run,
            "MATCH (dec:Decision {decision_id:$did}), (m:Mentor {mentor_id:$mid}) "
            "MERGE (dec)-[:TAKEN_BY]->(m)",
            {"did": "dec1", "mid": "m1"}
        )

    driver.close()
    print("✅ Seed data created in Neo4j.")


if __name__ == "__main__":
    build_seed_graph()