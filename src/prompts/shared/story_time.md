Story time is authoritative. `context.clock.current` contains the current
`world_time` (total elapsed minutes), one-based `day`, `time_24h` and `period`.
Use these engine-computed values instead of interpreting the integer as HHMM.
For example, 930 means Day 1 at 15:30; 1530 means Day 2 at 01:30, at night.
Periods use conventional clock ranges: night 22:00–06:00, morning 06:00–12:00,
afternoon 12:00–18:00, evening 18:00–22:00. They are not an astronomical model;
explicit world rules may establish unusual daylight. Otherwise, keep sunlight,
school activities and time-of-day descriptions consistent with the clock.
Historical prose is not authority to change the current time. If it conflicts,
ground this scene in the clock without inventing a time skip.
