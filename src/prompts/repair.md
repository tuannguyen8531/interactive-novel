# Structured output repair

Repair the invalid output for the named role. Preserve valid information when
possible, but obey the schema and semantic diagnostics below.

Role: {{role}}
Schema: {{schema_name}}
Diagnostics (JSON):
{{diagnostics}}

Preserve any configured story language identified by the invalid output or
diagnostics in all player-facing prose while repairing the structure. Keep JSON
field names, enum values and IDs unchanged.

Invalid output (JSON or text):
{{invalid_output}}

Return only one JSON object matching the requested schema. Do not add
explanation, Markdown fences, untyped claims or state mutations.
