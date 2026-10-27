# Creating a new mission

How to add a mission that the retail 1.16.5.0 client does not have. A new mission needs two
parts that must match:

- **Client**: its texts and table rows, added at runtime by this mod (`clientmod_data.py`).
- **Server**: its definition in Rasa.NET, added by an EF Core data migration.

The worked example is **Infinite Rasa Welcome** (mission `90000001`): the Rewards Verification
Officer in Alia Das offers it at level 1; you speak to him again; he pays 100 credits and one
Class I Basic Med Pack. Tested in game on 2026-10-20: offer, completion and reward work.

## 1. Pick ids

Use ids no retail mission, text or NPC package uses. This mod uses the **9xxxxxxx** range for
everything it adds. The retail client's highest ids are mission `20000003`, text `20000281` and
NPC package `2634`. Ids must stay below `2147483647` (the protocol checks `int.MaxValue`).

| What | Example | Notes |
| --- | --- | --- |
| Mission id | `90000001` | |
| Text ids | `90000001`–`90000013` | One per text. Group them per mission. |
| NPC package id | `90000001` | Only if the mission has a "talk to NPC" objective and that NPC has no package yet. One package per NPC: a shared package shows the topic at every NPC that has it. |

Check an id is free with the cross-reference tools (`pyo24.py` on the client tables) and in
the server's World database (`mission_content_definition`, `npc_package`).

## 2. Client side (this repo)

The client builds every mission text itself from four tables in `data/game.zip`. The server
sends only ids, never text. `mod/clientmod_loader.py` adds rows to these tables
when the client first loads them; `clientmod_data.py` holds the data.

| Client table | Key -> value | Used for |
| --- | --- | --- |
| `generated.client.missionconversation` | `(missionId, textType)` -> `[textId]` | Mission texts. Types (`missiontexttype`): 1 name, 2 log, 3 opening (offer), 4 finishing (turn-in), 5 reward, 6 reminder |
| `generated.client.missionobjective` | `(missionId, objectiveId)` -> `[(nameTextId, bodyTextId, counter0, counter1, counter2)]` | Objective name and description in the journal and tracker |
| `generated.client.objectiveconversation` | `(missionId, objectiveId, npcPackageId, playerFlagId, conversationType)` -> `[textId]` | What an NPC says when you complete an objective by talking. Types (`objectiveconversationtype`): 1 completion, 2 reminder, 3–6 choice body/options |
| `generated.client.language.<language>.missiontextlanguage` | `(textId, 1 or 2)` -> `[u'text']` | All the text. Every text is stored twice, keys 1 and 2. |

Add the mission to `clientmod_data.py`:

```python
TEXT_OVERRIDES = {'missiontextlanguage': {90000001: 'Infinite Rasa Welcome', ...}}

MISSIONS = {
    90000001: {
        'texts': {NAMETEXT: 90000001, LOGTEXT: 90000002, OPENINGTEXT: 90000003,
                  FINISHINGTEXT: 90000004, REMINDERTEXT: 90000006},
        'objectives': {1: (90000011, 90000012)},
        'conversations': {(1, 90000001, 1, COMPLETION): 90000013},
    },
}
```

Rules learned the hard way:

- **Texts must be unicode.** The client's text filter (`client/textfilter.py`,
  `FilterStaticText`) asserts on anything else, and the window then shows a wrong default label
  (we saw "Add Random Inventory Item"). The loader converts byte strings from UTF-8.
- `<br>` makes a line break in dialogue texts.
- Language tables load lazily (the first time a text is needed); the loader still catches them.
- Only the client's current language table is loaded; the texts are applied to whichever loads.
- A player without the mod sees "missing translation" texts for the mission.

Install with `./install.sh "<game folder>"` and restart the game. `client_mod.log` in the game
folder shows `mission 90000001: N <table> rows added` and `text missiontextlanguage <id> set`.

How these were found: `tools/pyo24dis.py` disassembles the client's Python 2.4 code, e.g.

```sh
tools/pyo24dis.py "<game>/trpython.zip" client/clientlanguagemanager.pyo _BuildMissionText BuildObjectiveConversationText
tools/pyo24dis.py "<game>/trpython.zip" --grep objectiveconversation
```

## 3. Server side (Rasa.NET)

Mission content is World data installed by EF Core migrations (Rasa.NET `docs/missions.md`,
`docs/mission-reference.md`). For the example see, in Rasa.NET:

- helper: `src/Rasa.DBL/Services/Preloader/Missions/InfiniteRasa/InfiniteRasaWelcomeV1.cs`
- migrations: `src/Rasa.DBL/Migrations/{Sqlite,MySql}World/20270124000000_Infinite_rasa_welcome.cs`
- branch: `quest_infinite_rasa_welcome`

Steps:

1. **One helper with `Up` and `Down`** that inserts the rows. Use your own `content_revision`
   (here `infinite_rasa_1`, at most 32 characters) and `requirement = Optional` on every row.
   Optional means a fault disables only this mission; `Required` (what the Wilderness helper
   writes) would stop the Game server from becoming ready.
2. **Rows**, in this order (foreign keys are checked at once):
   - `npc_package` for the NPC, if a conversation trigger needs a package it does not have
     (`id` = creature id, `package_id` = your package id).
   - `mission_content_definition`: `client_name_text_id`, `giver_id` and `receiver_id`
     (**creature** ids, e.g. 136, not spawn or package ids), `level`, `group_type` 1,
     `category_id` (a client category, e.g. 10000044), `shareable`, `abandonment_policy`.
   - `mission_objective_definition`: objective id, name and body text ids, `ordinal`,
     `initial_state` (Incomplete for the first objective), `is_required`.
   - `mission_reward_definition` (+ `mission_reward_item` per item; kind Fixed or Selectable).
   - `mission_objective_transition` (Incomplete -> Completed).
   - `mission_trigger`: what completes the objective. Kinds: Conversation (`npc_package_id`,
     `player_flag_id`), ProgressEvent (kill/item counters), ObjectiveState, AreaEntered,
     TimerElapsed.
   - `mission_action`: exactly one `GrantReward` (names the turn-in reward; it is paid at
     turn-in, not at once). Multi-objective missions add RevealObjective/ActivateObjective.
   - `MissionDataMigration.EnableMission(migration, missionId, revision)`. Only one revision of
     a mission may be enabled.
3. **A migration pair** with the same timestamp and class name, later than the newest World
   migration: `Migrations/SqliteWorld/<timestamp>_<Name>.cs` and `Migrations/MySqlWorld/...`.
   Data-only migrations have no Designer file, so put `[DbContext(typeof(SqliteWorldContext))]`
   (or `MySqlWorldContext`) and `[Migration("<timestamp>_<Name>")]` on the class, and call the
   helper from `Up`/`Down`.
   **Write the rows as plain SQL (`migration.Sql`), not `InsertData`/`UpdateData`.** Without a
   Designer file EF has no model to type them and the Game server stops at start with
   "There is no entity type mapped to the table ... which is used in a data operation".
   `InfiniteRasaWelcomeV1.Row` builds `INSERT` statements that SQLite and MySQL both accept.
4. **Build, run the mission tests, restart the Game server.** Migrations run at start.
   If a migration crashes, it leaves a row in the World database's `__EFMigrationsLock` and
   the next start waits forever ("applying 1 migration, please wait..." and no CPU use). Stop
   the server, back up the database, `DELETE FROM __EFMigrationsLock;`, fix, start again. Tests
   that pin the exact set of enabled missions (`WildernessCoverageTests`,
   `WildernessMigrationTests`) need the new mission added to their expectations.

What the server checks: text ids must be present (not that the client has them), giver and
receiver must exist, a Conversation trigger's package must exist in `npc_package`, rewards need
exactly one GrantReward. It keeps no list of client mission or text ids, so 9xxxxxxx ids pass.

**Without the migration:** `serverquery_addquest_welcome_infinite_rasa.sql` in this repo holds
the exact rows the migration writes, for adding the mission to a database by hand (server
stopped). Use the SQL file or the migration, not both. It was generated from the rows the
migration wrote and checked against a copy of the database from before the quest (SQLite).

## 4. How it plays (talk-to-NPC mission)

1. Talk to the giver: the offer window shows name + opening text (client) with the reward
   (server). Accepting sends `MissionGained`.
2. Talk again: the objective completion topic (`objectiveconversation`, completion text); the
   objective completes and the mission becomes completeable.
3. Talk to the receiver (same NPC here): the turn-in window shows the finishing text; the
   server pays the reward.
