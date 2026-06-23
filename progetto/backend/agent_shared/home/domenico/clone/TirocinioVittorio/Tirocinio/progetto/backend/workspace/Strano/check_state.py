#!/usr/bin/env python3
"""Generate all remaining Java lessons for the microlearning course.
This script constructs the module data and writes it directly to the course JSON."""

import json, os, sys

WORKSPACE = "/home/domenico/clone/TirocinioVittorio/Tirocinio/progetto/backend/workspace/Strano"
COURSE_FILE = os.path.join(WORKSPACE, "reports/microlearning_course.json")

# First, let's see what the current state of the course is
with open(COURSE_FILE) as f:
    course = json.load(f)

existing_mods = {m["id"] for m in course.get("moduli", [])}
existing_quiz = {q["id"] for q in course.get("quiz", [])}

print(f"Existing modules: {len(existing_mods)}")
print(f"Existing quiz: {len(existing_quiz)}")

# Point taglio data
with open(os.path.join(WORKSPACE, "reports/corso_plan.json")) as f:
    data = json.load(f)

pts = data["punti_taglio"]
print(f"Total punti_taglio: {len(pts)}")