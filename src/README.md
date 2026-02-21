# Graph Layer Documentation

<p align="center">
  <img src="../docs/graph-design.png" width="800" />
</p>


---

## 📚 Table of Contents

- [Overview](#overview)
- [Node Types](#node-types)
- [Relationship Model](#relationship-model)
- [How to Seed the Graph](#how-to-seed-the-graph)

---

## Overview

This folder contains the Neo4j graph layer for the assistant.

It defines:

- Core domain nodes (Student, Mentor, Goal, Assignment, etc.)
- Relationship structure between entities
- Seed logic to initialize a working graph
- Query functions used by retrieval and flow layers

---

## Node Types

### Student
Represents the primary user of the system.

**Key properties**
- `student_id` (unique)
- `name`
- `email`

---

### Mentor
Represents an authority who can approve or reject decisions.

**Key properties**
- `mentor_id` (unique)
- `name`

---

### Course
Represents a learning program.

**Key properties**
- `course_id` (unique)
- `title`

---

### Goal
Represents a student objective, typically tied to a course.

**Key properties**
- `goal_id` (unique)
- `title`
- `status`
- `progress_percent`

---

### Assignment
Represents a concrete task required to complete a goal or course.

**Key properties**
- `assignment_id` (unique)
- `title`
- `status`

---

### Deadline
Represents a due date for an assignment.

**Key properties**
- `deadline_id` (unique)
- `due_at`
- `type`

---

### Decision
Represents an action or ruling affecting learning flow (e.g., extension).

**Key properties**
- `decision_id` (unique)
- `decision_type`
- `status`
- `valid_until`

---

### Conversation
Represents a student interaction session.

**Key properties**
- `conversation_id` (unique)
- `started_at`
- `last_message`

---

### Intent
Represents inferred intent from a conversation.

**Key properties**
- `intent_id` (unique)
- `label`
- `confidence`

---

### Screen
Represents the current UI state of the student.

**Key properties**
- `screen_id` (unique)
- `name`

---

## Relationship Model

Key relationships:
```bash
(Student)-[:HAS_GOAL]->(Goal)

(Goal)-[:REQUIRES]->(Assignment)

(Assignment)-[:HAS_DEADLINE]->(Deadline)

(Student)-[:HAS_DECISION]->(Decision)

(Decision)-[:ABOUT]->(Assignment | Goal | Course)

(Decision)-[:TAKEN_BY]->(Mentor)

(Student)-[:HAS_CONVERSATION]->(Conversation)

(Conversation)-[:INFERRED_INTENT]->(Intent)

(Student)-[:CURRENT_SCREEN]->(Screen)

(Student)-[:ENROLLED_IN]->(Course)
```

<p align="center">
  <img src="../docs/seed-graph.png" width="800" />
</p>

## How to Seed the Graph

From the project root:

```bash
python -m src.graph.seed
```
