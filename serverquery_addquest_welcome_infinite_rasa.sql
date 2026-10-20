-- Infinite Rasa Welcome (mission 90000001): server side.
--
-- Adds the mission to a Rasa.NET World database by hand. These are the exact rows that the
-- Rasa.NET migration 20270124000000_Infinite_rasa_welcome writes (branch
-- quest_infinite_rasa_welcome, helper InfiniteRasaWelcomeV1.cs). Use either this file or that
-- migration, not both: the second one would fail on the duplicate rows.
--
-- What it adds:
--   - NPC package 90000001 for the Rewards Verification Officer in Alia Das (creature 136).
--     He had no package before.
--   - Mission 90000001, level 1, given and turned in by creature 136; one objective,
--     completed by speaking to him again; reward 100 credits and one Class I Basic Med Pack
--     (item template 44917), no experience. Revision 'infinite_rasa_1', rows Optional (2).
--
-- Players also need the client mod (clientmod_data.py): the retail client has no texts for it.
--
-- Works on SQLite and MySQL. Stop the Game server first, run this file, then start it again:
-- the server reads missions only at start.
--   SQLite: sqlite3 data/rasaworld.db < serverquery_addquest_welcome_infinite_rasa.sql
--
-- To remove it again (server stopped):
--   DELETE FROM mission_action               WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM mission_trigger              WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM mission_objective_transition WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM mission_reward_item          WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM mission_reward_definition    WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM mission_objective_definition WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM mission_content_definition   WHERE mission_id = 90000001 AND content_revision = 'infinite_rasa_1';
--   DELETE FROM npc_package                  WHERE id = 136;
-- Characters that had the mission keep their character-database rows for it.

BEGIN;

-- Parents before children: the foreign keys are checked at once.
INSERT INTO npc_package (id, package_id, comment)
    VALUES (136, 90000001, 'Rewards Verification Officer - Infinite Rasa Welcome');
INSERT INTO mission_content_definition (mission_id, content_revision, abandonment_policy, category_id, client_name_text_id, comment, enabled, giver_id, group_type, level, radio_completeable, receiver_id, requirement, shareable)
    VALUES (90000001, 'infinite_rasa_1', 1, 10000044, 90000001, 'Infinite Rasa Welcome', 1, 136, 1, 1, 0, 136, 2, 0);
INSERT INTO mission_objective_definition (mission_id, content_revision, objective_id, requirement, client_name_text_id, client_body_text_id, client_counter_0_text_id, client_counter_1_text_id, client_counter_2_text_id, ordinal, initial_state, is_required, comment)
    VALUES (90000001, 'infinite_rasa_1', 1, 2, 90000011, 90000012, NULL, NULL, NULL, 0, 1, 1, 'Speak to the Rewards Verification Officer');
INSERT INTO mission_reward_definition (mission_id, content_revision, reward_id, requirement, experience, credits, prestige, selection_count, comment)
    VALUES (90000001, 'infinite_rasa_1', 1, 2, 0, 100, 0, 0, 'Welcome gift');
INSERT INTO mission_reward_item (mission_id, content_revision, reward_id, item_id, kind, item_template_id, quantity, module_1, module_2, module_3, module_4)
    VALUES (90000001, 'infinite_rasa_1', 1, 1, 1, 44917, 1, 0, 0, 0, 0);
INSERT INTO mission_objective_transition (mission_id, content_revision, objective_id, transition_id, requirement, sequence, from_state, to_state, comment)
    VALUES (90000001, 'infinite_rasa_1', 1, 1, 2, 1, 1, 2, 'Objective 1 transition 1');
INSERT INTO mission_trigger (mission_id, content_revision, objective_id, transition_id, trigger_id, requirement, kind, sequence, related_objective_id, related_state, event_kind, subject_id, counter_id, initial_value, target_value, area_id, duration_seconds, npc_package_id, player_flag_id, source_spawn_resolved, comment)
    VALUES (90000001, 'infinite_rasa_1', 1, 1, 1, 2, 1, 1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 90000001, 1, NULL, 'Speak to the Rewards Verification Officer');
INSERT INTO mission_action (mission_id, content_revision, objective_id, transition_id, action_id, comment, indicator_id, item_intent, kind, npc_package_id, objective_state, player_flag_id, player_flag_value, requirement, reward_id, scenario_id, sequence, spawn_group_id, target_objective_id)
    VALUES (90000001, 'infinite_rasa_1', 1, 1, 1, 'Turn-in reward', NULL, NULL, 4, NULL, NULL, NULL, NULL, 2, 1, NULL, 1, NULL, NULL);

COMMIT;
