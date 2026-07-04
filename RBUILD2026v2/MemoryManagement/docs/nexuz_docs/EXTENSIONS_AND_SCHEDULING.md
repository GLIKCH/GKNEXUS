# Extensions And Scheduling

GLIKCH NEXUZ extensions are local extension request records stored in `MemoryManagement/docs/extensions.json`. They document developer, purpose, optional business, and authorization status before any future integration is trusted.

The Tasks and Dates calendar uses the existing local JSON task store at `MemoryManagement/docs/calendar_tasks.json`. Calendar days open a day event list first, then events can be created, edited, deleted, sorted, and saved. This keeps scheduling portable until a dedicated database is introduced.

Logo and visual settings are stored through the UI settings system and should remain separate from LM Studio and memory backend behavior.
