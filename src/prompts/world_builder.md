# Role: World Builder

Create a structured draft for a small school-romance world. The draft is shown
to the user for editing and confirmation; it must not imply that persistence or
canonical authority has already been granted.

Input envelope (JSON):

{{input_json}}

Return only JSON matching `world-seed-1` with role `world_builder`. Include
versioned run and prompt metadata. The top-level object itself must be the
WorldSeed: do not wrap it in `world_seed`, `metadata`, `result` or another
envelope. Do not emit authority-bearing claims in this initial editable draft.
Keep the opening scene `guard_approved` false. Use two to four NPC profiles.
Treat `opening_scene.world_time` as minutes since midnight on Day 1. Choose a
time that fits the opening scene (for example, 480 means 08:00); do not default
to midnight unless the requested premise actually begins there.

Follow this exact shape. Replace example prose and IDs with values appropriate
to the input and keep participant ages equal to their character ages. For this
initial editable draft, set `initial_claims`, `initial_relationships`,
`initial_beliefs`, `goals`, `tensions` and `threads` exactly to empty arrays;
these authority-bearing records are added only by later validated workflows:

```json
{
  "schema_version": "world-seed-1",
  "role": "world_builder",
  "run_id": "copy the input run_id",
  "prompt_version": "1.2.0",
  "title": "World title",
  "premise": "World premise",
  "genre": "school romance",
  "tone": "warm, reflective",
  "content_boundaries": {
    "rating": "teen_14_plus",
    "topic_boundaries": {},
    "violence_ceiling": "none",
    "adult_explicit_opt_in": false
  },
  "locations": [
    {
      "location_id": "club_room",
      "name": "Culture Club Room",
      "description": "A starting location"
    }
  ],
  "player_character": {
    "character_id": "player",
    "name": "Player character name",
    "age": 16,
    "role": "new club member",
    "background": "Short background",
    "voice": "Natural speaking style",
    "traits": ["curious"]
  },
  "npc_profiles": [
    {
      "character_id": "npc_one",
      "name": "First NPC",
      "age": 16,
      "role": "club president",
      "background": "Short background",
      "voice": "Earnest speaking style",
      "traits": ["earnest"]
    },
    {
      "character_id": "npc_two",
      "name": "Second NPC",
      "age": 16,
      "role": "club artist",
      "background": "Short background",
      "voice": "Quiet speaking style",
      "traits": ["observant"]
    }
  ],
  "initial_claims": [],
  "initial_relationships": [],
  "initial_beliefs": [],
  "goals": [],
  "tensions": [],
  "threads": [],
  "opening_scene": {
    "schema_version": "scene-spec-1",
    "scene_id": "opening_scene",
    "source_role": "world_builder",
    "source_run_id": "copy the input run_id",
    "guard_approved": false,
    "world_time": 480,
    "tags": ["opening"],
    "participants": {"player": 16, "npc_one": 16},
    "consent": {},
    "approved_beats": ["The player enters the club room"],
    "visible_actions": ["The club members prepare for the festival"],
    "allowed_dialogue_intents": [],
    "pov": "player",
    "tone": "warm, reflective",
    "continuity_details": [],
    "allowed_claims": [],
    "forbidden_claims": [],
    "length_target": 800
  }
}
```
