# Data the client mod adds to or changes in the client's tables.
# Python 2.4 syntax.

# Language table name -> {text id: new text}. Applied to that table in every client
# language when the table is first loaded. A text id the table does not have is added.
# Texts are made unicode (a byte string is read as UTF-8); the client accepts nothing else.
TEXT_OVERRIDES = {
    'missiontextlanguage': {
        # Test: objective name of "Lurking In The Shadows" (mission 427, objective 6).
        17243: 'Kill Proctor Fulgor. [client mod]',
    },
}
