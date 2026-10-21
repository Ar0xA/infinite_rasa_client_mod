# Data the client mod adds to or changes in the client's tables.
# Python 2.4 syntax.
#
# Id ranges: everything this mod adds uses 9xxxxxxx ids (missions, texts, NPC packages), far
# above the retail client's highest ids (mission 20000003, text 20000281, package 2634).
# See create_missions.md for how a mission is put together.

# Mission text types (generated.client.missiontexttype).
NAMETEXT = 1
LOGTEXT = 2
OPENINGTEXT = 3
FINISHINGTEXT = 4
REWARDTEXT = 5
REMINDERTEXT = 6

# Objective conversation types (generated.client.objectiveconversationtype).
COMPLETION = 1
REMINDER = 2

# Language table name -> {text id: text}. Applied to that table in every client language
# when the table is first loaded. A text id the table does not have is added.
# Texts are made unicode (a byte string is read as UTF-8); the client accepts nothing else.
TEXT_OVERRIDES = {
    'missiontextlanguage': {
        # Infinite Rasa Welcome (mission 90000001)
        90000001: 'Infinite Rasa Welcome',
        90000002: 'The Rewards Verification Officer in Alia Das has a welcome gift for you from '
                  'the Infinite Rasa team. Speak to him to collect it.',
        90000003: "Welcome to Alia Das, recruit!<br><br>On behalf of the Infinite Rasa team: "
                  "thank you for joining the fight against the Bane. The AFS takes care of its "
                  "own, and I have a little something to get you started.<br><br>Say the word "
                  "and it's yours.",
        90000004: "There you go: a med pack and some credits. Stay alive out there, recruit, "
                  "and welcome to Infinite Rasa!",
        90000006: 'Talk to me to collect your welcome gift, recruit.',
        90000011: 'Speak to the Rewards Verification Officer.',
        90000012: 'Speak to the Rewards Verification Officer in Alia Das to collect your welcome gift.',
        90000013: "Good to see you again. Your welcome gift is ready - sign here and it's yours.",
    },
}

# Mission id -> its rows in the client's mission tables:
#   'texts':         {mission text type: text id}                   -> missionconversation
#   'objectives':    {objective id: (name text id, body text id)}   -> missionobjective
#   'conversations': {(objective id, npc package id, player flag, conversation type): text id}
#                                                                    -> objectiveconversation
# The server side (ids, giver, package, reward) must match: Rasa.NET
# src/Rasa.DBL/Services/Preloader/Missions/InfiniteRasa/.
MISSIONS = {
    90000001: {
        'texts': {
            NAMETEXT: 90000001,
            LOGTEXT: 90000002,
            OPENINGTEXT: 90000003,
            FINISHINGTEXT: 90000004,
            REMINDERTEXT: 90000006,
        },
        'objectives': {
            1: (90000011, 90000012),
        },
        'conversations': {
            # The Rewards Verification Officer (creature 136) has NPC package 90000001.
            (1, 90000001, 1, COMPLETION): 90000013,
        },
    },
}

# Movable windows (clientmod_movable.py): drag a window with Ctrl + left mouse button
# (the client never sees ALT on a mouse click).
# Positions are saved in client_mod_windows.txt in the game folder; delete it to reset.
MOVABLE_WINDOWS = True
# client/ui modules whose windows stay where the game puts them.
MOVABLE_EXCLUDED = (
    'reticlewindow',            # the crosshair follows the screen centre
    'charactercreationwindow',  # character creation / selection screen
)

# Native modules: .pyd files (32-bit DLLs for Python 2.4) in python_nca_internal, imported
# at boot by clientbootstrap._load_native_modules. A missing or broken one only logs a line.
# See native_modules.md. Off by default: build the example with native/build.sh and remove
# the '#' to load it (it logs from native code and tags the game window title).
NATIVE_MODULES = (
    # 'clientmod_native',
)
