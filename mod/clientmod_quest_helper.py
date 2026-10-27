# GM quest helper: drives the character from a command file, for testing quests faster.
#
# Experimental. Python 2.4: no 'with', no conditional expressions, no 'except X as e',
# no any()/all().
#
# A program outside the game (or you, with a text editor) writes commands, one per line, to
# quest_helper_cmd.txt in the game folder. A few times a second the helper reads the file,
# deletes it and runs the commands in order. Write the file in one go (write a temporary file
# and rename it), so the game never reads half of it.
#
# What the helper sees is written to quest_helper_state.txt (rewritten every second) and each
# command's result to client_mod.log ("quest: ...").
#
# Commands (entity ids are the decimal ids the server uses):
#   say <text>              send <text> as if typed in chat: ".teleport 1 2 3 1220", "/givemission 5"
#   gm on | gm off          GM test mode: ".invisible on" and ".immune all", or both off
#   invisible on|off        ".invisible on|off"
#   immune <args>           ".immune <args>" on yourself: all, off, or damage types
#   target <entityId>       target an entity
#   untarget                clear the target
#   goto <x> <y> <z> [range]       walk to a position (y is up), stop within range (default 1)
#   walkto <entityId> [range]      walk to an entity (default range 1.5)
#   use [entityId]          use an entity (default: the target), walking to it first if needed
#   stop                    stop walking
#   accept | decline        the open conversation's mission: accept or decline
#   complete [n]            the open conversation's Complete button. A turn-in with a reward
#                           choice is completed with the choice: reward n is picked first
#                           (default 1, as numbered in the state file), as the client wants
#   turnin [n]              the same as complete [n]
#   pick <n>                pick reward n, without completing
#   reward [n]              Accept Reward: only for a mission that is already a success (the
#                           client's separate reward window); picks reward n first like complete
#   choice <n>              pick choice n (from 1) of the open conversation, as listed in the state
#   wait <ms>               wait before the next command
#   waitworld               wait until the character is in the world (after a map load or a
#                           teleport with a map id: the server is not ready before that)
#   near [radius]           list the entities within radius (default 30 m): id, class, name
#   usename <text>          walk to the nearest entity whose name has <text> and use it
#   ability <n>             fire hotkey bar slot n (1-5) at the target, as pressing key n does
#   loot <entityId>         walk to a corpse and take everything (Loot All)
#   kill <entityId> [slot] [seconds]
#                           target it, get within KILL_RANGE, fire slot (default 1) every
#                           KILL_INTERVAL_MS until it is dead (at most seconds, default 90),
#                           then loot it. The next command waits for this to end.
#   tele <entityId>         ".tele" to the entity's position, without a map load (out of a stuck spot)
#   reload                  load this file again, without a game restart
#   camera <degrees>        turn the camera to that yaw (0 = +z), as the turn keys do
#   look <entityId> [deg]   turn the camera from the player towards the entity (plus deg, to see past the player)
#   py <expression>         evaluate a Python expression in the client and log its value (test aid)
#   hide <entityId>         make only that entity invisible here (opacity 0, scale 0.001); unhide undoes it
#   probe <entityId>        log what the client knows about drawing it: culled, loading, opacity, size
#   dismiss                 close every open message box (server error dialogs) without input
#   zoom on|off             the zoom camera (about 2 m behind the shoulder) or the normal one
#   ui off|on               the client's screenshot mode (no windows or HUD), or the normal view
#   killname <text> [slot] [seconds]
#                           kill the nearest living entity within 80 m whose name has <text>
#
# Account level 10 only. The client is not told the account level (SetIsGM is a yes or no),
# so when a character enters the world the helper sends ".flag list", a read-only command that
# needs level 10, and reads the server's answer in chat:
#   "No server flags are set." / "Set: ..."          level 10: the helper runs
#   ".flag needs account level 10; yours is N."      lower: the helper stays off
#   "Unknown command: .flag"                          a player: the helper stays off
# Until the answer comes, commands wait; without an answer in PROBE_TIMEOUT_MS the helper stays
# off. This is a convenience, not security: the server checks every GM command anyway.
#
# GM test mode: with QUEST_HELPER_GM_MODE in clientmod_data, "gm on" is sent by itself each
# time a character enters the world. The server turns .invisible off at every login and an
# immunity lives on the character only until it logs out. "gm off" turns both off, for a test
# that needs the character seen or hurt; the next login turns them on again.

import os
import sys
import math
import time

CMD_FILE = 'quest_helper_cmd.txt'
STATE_FILE = 'quest_helper_state.txt'
POLL_MS = 250
STATE_MS = 1000
# The server's /immune acts on the target; after clearing the target, wait for the server to
# hear of it before sending the command.
UNTARGET_WAIT_MS = 500

_log = None
_queue = []             # commands still to run: strings
# The helper's state survives "reload": kept on sys, put back at the end of this file.
_KEPT = ('_log', '_queue', '_results', '_manifestation', '_window', '_allowed', '_probe_age')
_wait_until = [0.0]     # time.time() before which no command runs
_since_poll = [0]
_since_state = [0]
_results = []           # the last results, newest last
_manifestation = [None]  # the entity id the GM mode was last applied to
_window = [None]        # the conversation window (client.ui.conversationwindow), once shown

REQUIRED_LEVEL = 10
PROBE_COMMAND = '.flag list'
PROBE_TIMEOUT_MS = 10000
# The account level check: None while waiting for the answer, True or False once known.
_allowed = [None]
_probe_age = [None]     # ms since the probe was sent; None when no probe is out
# waitworld: None, or [started (time.time()), seen the character leave, time it came back]
_world_wait = [None]
WORLD_LEAVE_S = 5.0     # how long to look for the character to leave (a map load)
WORLD_SETTLE_S = 3.0    # how long the character must be back before the next command
WORLD_TIMEOUT_S = 90.0
KILL_RANGE = 15.0
KILL_INTERVAL_MS = 1500
# A camera turn stops within this many radians of the wanted yaw.
LOOK_TOLERANCE = math.radians(4)
# kill: None, or {'id', 'slot', 'until', 'next', 'walking'}
_kill = [None]
# A camera turn in progress: {'yaw', 'dir' (-1 left, 1 right), 'until'}.
_look = [None]
# Entities taken out of the world by 'hide'.
_hidden = {}
# True while 'ui off' holds the windows hidden.
_ui_hidden = [False]


def _say(message):
    if _log is not None:
        _log('quest: %s' % (message,))
    _results.append('%s %s' % (time.strftime('%H:%M:%S'), message))
    del _results[:-20]


# --- client access --------------------------------------------------------------------------

def _player():
    import client.gameuiutil
    return client.gameuiutil.GetManifestation()


def _entity(entity_id):
    import client.entitymanager
    return client.entitymanager.GetEntity(entity_id)


def _position(entity):
    try:
        return tuple(entity.body.GetPosition())
    except:
        return None


def _name(entity):
    try:
        return entity.GetName()
    except:
        return '?'


def _chat(text):
    import client.communicator
    import generated.client.chatdata as chatdata
    if not isinstance(text, unicode):
        text = text.decode('utf-8')
    client.communicator.OnProcessChat(text, chatdata.RADIAL, None)


def _untarget():
    import client.targeting
    client.targeting.ClearDirectTarget(True)


def _target():
    import client.targeting
    return client.targeting.GetDirectTarget()


def _private(obj, name):
    # A double-underscore attribute of a conversationwindow instance.
    return getattr(obj, '_conversationwindow__' + name, None)


# --- commands -------------------------------------------------------------------------------

def _gm_mode(on):
    if on:
        _queue[0:0] = ['untarget', 'wait %d' % UNTARGET_WAIT_MS, 'say .invisible on', 'say .immune all']
    else:
        _queue[0:0] = ['untarget', 'wait %d' % UNTARGET_WAIT_MS, 'say .invisible off', 'say .immune off']


def _cmd_say(args):
    _chat(args)
    return 'said %s' % (args,)


def _cmd_gm(args):
    if args not in ('on', 'off'):
        return 'gm: on or off'
    _gm_mode(args == 'on')
    return 'gm %s queued' % (args,)


def _cmd_invisible(args):
    _chat('.invisible %s' % (args,))
    return 'invisible %s sent' % (args,)


def _cmd_immune(args):
    _queue[0:0] = ['wait %d' % UNTARGET_WAIT_MS, 'say .immune %s' % (args,)]
    _untarget()
    return 'immune %s queued' % (args,)


def _cmd_target(args):
    import client.targeting
    entity_id = long(args)
    if client.targeting.SetDirectTarget(entity_id):
        return 'target %d (%s)' % (entity_id, _name(_entity(entity_id)))
    return 'target %d: not targetable or not here' % (entity_id,)


def _cmd_untarget(args):
    _untarget()
    return 'untargeted'


def _arrived(in_range, *args):
    _say('arrived, in range %s' % (in_range,))


def _cmd_goto(args):
    parts = args.split()
    position = (float(parts[0]), float(parts[1]), float(parts[2]))
    reach = 1.0
    if len(parts) > 3:
        reach = float(parts[3])
    _player().TrackMoveToPosition(position, reach, _arrived, ())
    return 'walking to %s' % (position,)


def _cmd_walkto(args):
    parts = args.split()
    entity_id = long(parts[0])
    reach = 1.5
    if len(parts) > 1:
        reach = float(parts[1])
    if _entity(entity_id) is None:
        return 'walkto %d: not here' % (entity_id,)
    _player().TrackEntityMoveNextTo(entity_id, reach, _arrived, (entity_id,))
    return 'walking to %d (%s)' % (entity_id, _name(_entity(entity_id)))


def _use_now(entity_id):
    entity = _entity(entity_id)
    if entity is None:
        _say('use %d: gone' % (entity_id,))
        return
    action = entity.GetUseAction()
    if action is None:
        _say('use %d (%s): no use action' % (entity_id, _name(entity)))
        return
    action()
    _say('used %d (%s)' % (entity_id, _name(entity)))


def _really_there(what, entity_id, reach):
    # The walk reports "in range" also when it ended against a wall: check the distance.
    distance = _distance_to(_entity(entity_id))
    if distance is not None and distance > reach:
        _say('%s %d: the walk stopped %.1f m away (blocked?); try "tele %d"' % (what, entity_id, distance, entity_id))
        return False
    return True


def _use_after_walk(in_range, entity_id):
    if not in_range:
        _say('use %d: could not get there' % (entity_id,))
        return
    if not _really_there('use', entity_id, 5.0):
        return
    # As the game does: pause so the server knows the player has stopped (gameui.py).
    import client.entitymanager
    client.entitymanager.AddCallback(None, _use_now, args=(entity_id,), delayTimeMs=250)


def _cmd_use(args):
    if args:
        entity_id = long(args)
    else:
        entity_id = _target()
    if not entity_id:
        return 'use: no entity id and no target'
    entity = _entity(entity_id)
    if entity is None:
        return 'use %d: not here' % (entity_id,)
    player = _player()
    if player.IsInInteractionRange(entity):
        _use_now(entity_id)
        return 'use %d' % (entity_id,)
    player.TrackEntityMoveNextTo(entity_id, 1.5, _use_after_walk, (entity_id,))
    return 'walking to %d (%s) to use it' % (entity_id, _name(entity))


def _cmd_stop(args):
    _player().StopTracking()
    return 'stopped'


def _button(method):
    window = _window[0]
    if window is None:
        return 'no conversation window yet'
    # Read the mission first: the button closes the window, which forgets it.
    mission = _private(window, 'missionId')
    getattr(window, method)(None, None)
    return '%s pressed (mission %s)' % (method, mission)


def _cmd_accept(args):
    return _button('OnAcceptMissionBtn')


def _cmd_decline(args):
    return _button('OnDeclineMissionBtn')


def _pick_if_needed(args):
    window = _window[0]
    if window is not None and _private(window, 'bChooseRewards') and _private(window, 'rewardSelection') is None:
        number = 1
        if args:
            number = int(args)
        _say(_cmd_pick('%d' % (number,)))


def _cmd_complete(args):
    _pick_if_needed(args)
    return _button('OnCompleteBtn')


def _rewards():
    # The reward choices of the open window: [(selection index, item template id)], in the
    # order the window numbers them. Fixed rewards (no selection index) are not choices.
    window = _window[0]
    if window is None:
        return []
    widgets = _private(window, 'itemWidgets') or {}
    found = []
    for info, index in widgets.values():
        if index is not None:
            found.append((index, info[0]))
    found.sort()
    return found


def _cmd_pick(args):
    window = _window[0]
    if window is None:
        return 'no conversation window yet'
    choices = _rewards()
    number = int(args)
    if number < 1 or number > len(choices):
        return 'pick %s: there are %d reward choices' % (args, len(choices))
    index, template = choices[number - 1]
    window._SetSelectedReward(index)
    return 'reward %d picked (item template %s)' % (number, template)


def _cmd_reward(args):
    window = _window[0]
    if window is None:
        return 'no conversation window yet'
    _pick_if_needed(args)
    return _button('OnAcceptRewardBtn')


def _cmd_turnin(args):
    return _cmd_complete(args)


class _Choice:
    # Stands in for the toggled choice widget OnConversationChoiceSelected expects.
    def __init__(self, key):
        self.key = key

    def IsToggled(self):
        return True

    def GetParent(self):
        return self.key


def _choices():
    window = _window[0]
    if window is None:
        return []
    choices = _private(window, 'convoChoice') or {}
    items = [(repr(value), key, value) for key, value in choices.items()]
    items.sort()
    return [(key, value) for (text, key, value) in items]


def _cmd_choice(args):
    index = int(args) - 1
    choices = _choices()
    if index < 0 or index >= len(choices):
        return 'choice %s: there are %d choices' % (args, len(choices))
    key, value = choices[index]
    _window[0].OnConversationChoiceSelected(_Choice(key), None)
    return 'choice %d picked: %r' % (index + 1, value)


def _entities_near(radius):
    import client.entitymanager
    player = _player()
    here = _position(player)
    if here is None:
        return []
    found = []
    for entity in client.entitymanager.g_entityManager.GetAllEntities():
        if entity is player:
            continue
        where = _position(entity)
        if where is None:
            continue
        dx = where[0] - here[0]
        dz = where[2] - here[2]
        distance = (dx * dx + dz * dz) ** 0.5
        if distance <= radius:
            found.append((distance, entity))
    found.sort()
    return found


def _cmd_near(args):
    radius = 30.0
    if args:
        radius = float(args)
    found = _entities_near(radius)
    for distance, entity in found[:40]:
        usable = 'use'
        try:
            if entity.GetUseAction() is None:
                usable = '-'
        except:
            usable = '?'
        where = _position(entity)
        _say('  %s class %s %s %.1f m %s at %.1f %.1f %.1f' % (getattr(entity, 'entityId', '?'), getattr(entity, 'classId', '?'),
                                                         _name(entity), distance, usable, where[0], where[1], where[2]))
    return '%d entities within %.0f m' % (len(found), radius)


def _cmd_usename(args):
    text = args.lower()
    for distance, entity in _entities_near(200.0):
        name = _name(entity)
        try:
            name = name.lower()
        except:
            continue
        if name.find(text) >= 0:
            return _cmd_use('%d' % (entity.entityId,))
    return 'usename: no entity named like %r within 200 m' % (args,)


def _cmd_waitworld(args):
    _world_wait[0] = [time.time(), False, None]
    return 'waiting for the world'


def _world_ready():
    # True when no waitworld is pending, or the one pending is over.
    wait = _world_wait[0]
    if wait is None:
        return True
    now = time.time()
    present = _player() is not None and _position(_player()) is not None
    if not present:
        wait[1] = True
        wait[2] = None
    elif wait[1] or now - wait[0] >= WORLD_LEAVE_S:
        if wait[2] is None:
            wait[2] = now
        elif now - wait[2] >= WORLD_SETTLE_S:
            _world_wait[0] = None
            _say('in the world (after %.1f s)' % (now - wait[0],))
            return True
    if now - wait[0] >= WORLD_TIMEOUT_S:
        _world_wait[0] = None
        del _queue[:]
        _say('waitworld: no world after %.0f s; the commands after it are dropped' % (WORLD_TIMEOUT_S,))
    return False


def _fire(slot):
    # gameui.StartAbilityAction + FinishAbilityAction (key n down, key n up), aimed at the
    # target: FinishAbilityAction aims at the mouse-over target, the helper has no mouse.
    from shared.gameconstants import NUM_ABILITY_DRAWER_SLOTS
    actor = _player()
    if actor is None or actor.IsChargingWeapon():
        return 'not now'
    target = _target()
    if not target:
        return 'no target'
    actor.SendRequestedAbilityDrawerSlot()
    index = (slot - 1) + actor.GetAbilityDrawerLoadoutIdx() * NUM_ABILITY_DRAWER_SLOTS
    actor.StartTargetingAbility(index)
    if actor.IsTargetingAbility():
        actor.PerformTargetingAbility(target, 1)
        return 'slot %d at %s' % (slot, target)
    return 'slot %d did not start (cooldown, power or no ability there)' % (slot,)


def _cmd_ability(args):
    return _fire(int(args))


def _loot_now(entity_id):
    entity = _entity(entity_id)
    if entity is None or not hasattr(entity, 'LootAll'):
        _say('loot %s: no corpse to loot' % (entity_id,))
        return
    entity.LootAll()
    _say('loot all from %s (%s)' % (entity_id, _name(entity)))


def _loot_after_walk(in_range, entity_id):
    if not in_range:
        _say('loot %s: could not get there' % (entity_id,))
        return
    if not _really_there('loot', entity_id, 5.0):
        return
    import client.entitymanager
    client.entitymanager.AddCallback(None, _loot_now, args=(entity_id,), delayTimeMs=250)


def _cmd_loot(args):
    entity_id = long(args)
    if _entity(entity_id) is None:
        return 'loot %d: not here' % (entity_id,)
    _player().TrackEntityMoveNextTo(entity_id, 1.5, _loot_after_walk, (entity_id,))
    return 'walking to %d to loot it' % (entity_id,)


def _distance_to(entity):
    a = _position(_player())
    b = _position(entity)
    if a is None or b is None:
        return None
    dx = a[0] - b[0]
    dz = a[2] - b[2]
    return (dx * dx + dz * dz) ** 0.5


def _dead(entity):
    try:
        return entity.IsDead()
    except:
        return False


def _cmd_kill(args):
    parts = args.split()
    entity_id = long(parts[0])
    slot = 1
    seconds = 90
    if len(parts) > 1:
        slot = int(parts[1])
    if len(parts) > 2:
        seconds = int(parts[2])
    entity = _entity(entity_id)
    if entity is None:
        return 'kill %d: not here' % (entity_id,)
    import client.targeting
    client.targeting.SetDirectTarget(entity_id)
    now = time.time()
    _kill[0] = {'id': entity_id, 'slot': slot, 'until': now + seconds, 'next': now, 'walking': False, 'shots': 0}
    return 'killing %d (%s) with slot %d' % (entity_id, _name(entity), slot)


def _cmd_killname(args):
    parts = args.split()
    text = parts[0].lower()
    rest = ' '.join(parts[1:])
    for distance, entity in _entities_near(80.0):
        try:
            name = _name(entity).lower()
        except:
            continue
        if name.find(text) >= 0 and not _dead(entity) and hasattr(entity, 'IsDead'):
            return _cmd_kill(('%d %s' % (entity.entityId, rest)).strip())
    return 'killname: nothing alive named like %r within 80 m' % (parts[0],)


def _kill_step():
    # True while a kill is going on: the queue waits for it.
    kill = _kill[0]
    if kill is None:
        return False
    now = time.time()
    entity = _entity(kill['id'])
    if entity is None:
        _kill[0] = None
        _say('kill %d: it is gone (%d shots)' % (kill['id'], kill['shots']))
        return False
    if _dead(entity):
        _kill[0] = None
        _say('kill %d: dead after %d shots; looting' % (kill['id'], kill['shots']))
        _queue[0:0] = ['wait 1500', 'loot %d' % (kill['id'],)]
        return False
    if now >= kill['until']:
        _kill[0] = None
        _say('kill %d: still alive after the time allowed (%d shots)' % (kill['id'], kill['shots']))
        return False
    distance = _distance_to(entity)
    if distance is not None and distance > KILL_RANGE:
        if not kill['walking']:
            kill['walking'] = True
            _player().TrackEntityMoveNextTo(kill['id'], KILL_RANGE - 3.0, None, None)
        return True
    if kill['walking']:
        kill['walking'] = False
        _player().StopTracking()
    if now >= kill['next']:
        kill['next'] = now + KILL_INTERVAL_MS / 1000.0
        import client.targeting
        if _target() != kill['id']:
            client.targeting.SetDirectTarget(kill['id'])
        result = _fire(kill['slot'])
        kill['shots'] += 1
        if kill['shots'] == 1 or kill['shots'] % 5 == 0:
            _say('kill %d: shot %d: %s' % (kill['id'], kill['shots'], result))
    return True


def _cmd_tele(args):
    entity = _entity(long(args))
    where = _position(entity)
    if where is None:
        return 'tele %s: not here' % (args,)
    # 1.5 m beside it, 1 m up: not inside it.
    _chat('.tele %.1f %.1f %.1f' % (where[0] + 1.5, where[1] + 1.0, where[2]))
    return 'tele to %s (%s) at %.1f %.1f %.1f' % (args, _name(entity), where[0], where[1], where[2])


def _gameclient():
    # The engine object: the retail modules use it as a global they never import (the engine puts it
    # into their namespace), e.g. client.inputstate.wonkavator. Take it from one that has it.
    for name in ('client.inputstate.wonkavator', 'client.gameui', 'client.gameuiutil'):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, 'gameclient'):
            return module.gameclient
    for module in sys.modules.values():
        if module is not None and hasattr(module, 'gameclient'):
            return module.gameclient
    raise ImportError('no module has gameclient')


def _camera_yaw():
    # The camera's yaw in radians, atan2(x, z) of the look vector (0 = +z).
    return _gameclient().GetGameUIManager().GetDisplayWorld().GetCameraDir()[0]


def _yaw_diff(target, current):
    d = target - current
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return d


def _camera_pitch():
    return _gameclient().GetGameUIManager().GetDisplayWorld().GetCameraDir()[1]


def _start_turn(yaw, what, target=None):
    # Turn the camera as the turn keys do (UserController.TurnLeft/TurnRight), then, with a target
    # position, tilt it (LookUp/LookDown) towards it; both stopped in _look_step.
    _look[0] = {'yaw': yaw, 'dir': 0, 'until': time.time() + 10.0, 'what': what, 'phase': 'yaw', 'target': target}
    return 'turning to %.1f degrees (%s)' % (math.degrees(yaw), what)


def _stop_keys(look, controller):
    if look['phase'] == 'yaw':
        if look['dir'] > 0:
            controller.TurnRight(False)
        elif look['dir'] < 0:
            controller.TurnLeft(False)
    else:
        if look['dir'] > 0:
            controller.LookDown(False)
        elif look['dir'] < 0:
            controller.LookUp(False)
    look['dir'] = 0


def _look_step():
    # True while a camera turn is going on: the queue waits for it.
    look = _look[0]
    if look is None:
        return False
    controller = _gameclient().GetUserController()
    if look['phase'] == 'yaw':
        if look['target'] is not None:
            # Aim from the camera, not from the player: the camera stands behind or beside the player and
            # moves while it turns, so a near entity needs the angle measured again at each step.
            camera = controller.GetCameraPosition()
            there = look['target']
            look['yaw'] = math.atan2(there[0] - camera[0], there[2] - camera[2]) + look.get('offset', 0.0)
        d = _yaw_diff(look['yaw'], _camera_yaw())
    else:
        d = look['pitch'] - _camera_pitch()
    if abs(d) < LOOK_TOLERANCE or time.time() > look['until']:
        _stop_keys(look, controller)
        if look['phase'] == 'yaw' and look['target'] is not None:
            camera = controller.GetCameraPosition()
            there = look['target']
            flat = math.sqrt((there[0] - camera[0]) ** 2 + (there[2] - camera[2]) ** 2)
            # The client's pitch grows downwards (LookDown makes it bigger).
            look['pitch'] = math.atan2(camera[1] - there[1], max(flat, 0.1))
            look['phase'] = 'pitch'
            look['until'] = time.time() + 6.0
            return True
        _look[0] = None
        _say('look: %s, off by %.1f degrees (%s)' % (look['what'], math.degrees(d), look['phase']))
        return False
    want = 1
    if d < 0:
        want = -1
    if want != look['dir']:
        _stop_keys(look, controller)
        if look['phase'] == 'yaw':
            if want > 0:
                controller.TurnRight(True)
            else:
                controller.TurnLeft(True)
        else:
            if want > 0:
                controller.LookDown(True)
            else:
                controller.LookUp(True)
        look['dir'] = want
    return True


def _cmd_camera(args):
    return _start_turn(math.radians(float(args)), 'yaw %s' % (args,))


def _cmd_look(args):
    # look <entityId> [offset degrees]: turn the camera from the player towards the entity; an offset
    # turns it that much further, so the player's own body is not between the camera and the entity.
    parts = args.split()
    entity = _entity(long(parts[0]))
    offset = 0.0
    if len(parts) > 1:
        offset = math.radians(float(parts[1]))
    there = _position(entity)
    here = _position(_player())
    if there is None or here is None:
        return 'look %s: not here' % (args,)
    yaw = math.atan2(there[0] - here[0], there[2] - here[2]) + offset
    answer = _start_turn(yaw, '%s (%s), %.1f m' % (args, _name(entity),
                         math.sqrt((there[0] - here[0]) ** 2 + (there[2] - here[2]) ** 2)), there)
    _look[0]['offset'] = offset
    return answer


def _cmd_frame(args):
    # frame <entityId> [metres]: teleport the player that far from the entity (default 6 m), on the line
    # from the entity to where the player stands now, so a following "look" sees it from a set distance.
    parts = args.split()
    entity = _entity(long(parts[0]))
    distance = 6.0
    if len(parts) > 1:
        distance = float(parts[1])
    there = _position(entity)
    here = _position(_player())
    if there is None or here is None:
        return 'frame %s: not here' % (args,)
    dx = here[0] - there[0]
    dz = here[2] - there[2]
    flat = math.sqrt(dx * dx + dz * dz)
    if flat < 0.1:
        dx, dz, flat = 1.0, 0.0, 1.0
    x = there[0] + dx / flat * distance
    z = there[2] + dz / flat * distance
    _chat('.tele %.1f %.1f %.1f' % (x, there[1] + 1.0, z))
    return 'frame %s (%s): player to %.1f %.1f %.1f, %.1f m from it' % (parts[0], _name(entity), x, there[1] + 1.0, z, distance)


def _cmd_hide(args):
    # hide <entityId>: take only this entity out of this client's world, for a before/after picture.
    # Opacity and scale do not hide every object (a mission item on the ground stays): removal does.
    entity = _entity(long(args))
    if entity is None:
        return 'hide %s: not here' % (args,)
    _hidden[long(args)] = True
    entity.body.RemoveFromWorld()
    return 'hidden %s (%s)' % (args, _name(entity))


def _cmd_unhide(args):
    # Puts the entity back the way the client adds it (client.world.AddToWorld: body.AddToWorld(entity.flags)).
    entity = _entity(long(args))
    _hidden.pop(long(args), None)
    if entity is None:
        return 'unhide %s: not here' % (args,)
    import client.world
    client.world.AddToWorld(entity)
    return 'shown %s (%s), in world %s' % (args, _name(entity), entity.body.IsInWorld())


def _cmd_probe(args):
    # probe <entityId>: what the client knows about drawing it.
    entity = _entity(long(args))
    if entity is None:
        return 'probe %s: not in the client' % (args,)
    body = entity.body
    here = _position(_player())
    there = _position(entity)
    distance = -1.0
    if here is not None and there is not None:
        distance = math.sqrt(sum([(there[i] - here[i]) ** 2 for i in range(3)]))
    return 'probe %s (%s): culled %s, loading %s, opacity %s, in world %s, radius %.2f, extents %s, at %s, %.1f m' % (
        args, _name(entity), body.IsCulled(), body.IsLoading(), body.GetOpacity(), body.IsInWorld(),
        body.GetBoundingRadius(), body.GetExtents(), there, distance)


def _cmd_dismiss(args):
    # dismiss: close every open message box (e.g. "Server Map Initialization Errors!") without input.
    import client.gameui
    ids = list(getattr(client.gameui, 'g_messageBoxIds', []) or [])
    for box in ids:
        try:
            client.gameui.DestroyMessageBox(box)
        except:
            _say('dismiss %s failed: %s' % (box, sys.exc_info()[1]))
    return 'closed %d message box(es): %s' % (len(ids), ids)


def _cmd_ui(args):
    # ui off|on: the client's screenshot mode (the ToggleUI key, GameUIManager.ToggleScreenshotMode):
    # no windows, HUD or tutorials in the picture; on undoes it.
    want = args.strip().lower() != 'off'
    if want == _ui_hidden[0]:
        _gameclient().GetGameUIManager().ToggleScreenshotMode()
        _ui_hidden[0] = not want
    return 'ui %s' % (want and 'on' or 'off',)


def _cmd_zoom(args):
    # zoom on|off: the client's zoom camera (about 2 m behind the shoulder) or the normal one (about 15 m).
    controller = _gameclient().GetUserController()
    want = args.strip().lower() != 'off'
    if bool(controller.IsCameraZoomed()) != want:
        controller.ToggleCameraZoom()
    return 'zoom %s' % (want and 'on' or 'off',)


def _cmd_py(args):
    # py <expression>: evaluate in the client (a test aid: the command file is local to the game folder).
    space = {'gameclient': _gameclient(), 'player': _player(), 'entity': _entity, 'math': math, 'sys': sys}
    return repr(eval(args, space))[:1500]


def _cmd_reload(args):
    import clientmod_quest_helper
    import client.gameui
    import client.ui.uieventmanager as uieventmanager
    old_update = _update
    old_chat = _on_chat_message
    sys._quest_helper_kept = dict([(name, globals()[name]) for name in _KEPT])
    reload(clientmod_quest_helper)
    if old_update in client.gameui.g_updateCallables:
        client.gameui.UnregisterForUpdate(old_update)
    client.gameui.RegisterForUpdate(clientmod_quest_helper._update)
    handlers = getattr(uieventmanager, 'g_handlersForAny', {}).get(uieventmanager.UI_DISPLAY_CHAT_MESSAGE, [])
    if old_chat in handlers:
        handlers.remove(old_chat)
    return 'reloaded'


def _cmd_wait(args):
    _wait_until[0] = time.time() + int(args) / 1000.0
    return 'waiting %s ms' % (args,)


COMMANDS = {
    'say': _cmd_say, 'gm': _cmd_gm, 'invisible': _cmd_invisible, 'immune': _cmd_immune,
    'target': _cmd_target, 'untarget': _cmd_untarget, 'goto': _cmd_goto, 'walkto': _cmd_walkto,
    'use': _cmd_use, 'stop': _cmd_stop, 'accept': _cmd_accept, 'decline': _cmd_decline,
    'complete': _cmd_complete, 'reward': _cmd_reward, 'choice': _cmd_choice, 'wait': _cmd_wait,
    'waitworld': _cmd_waitworld, 'near': _cmd_near, 'usename': _cmd_usename,
    'ability': _cmd_ability, 'loot': _cmd_loot, 'kill': _cmd_kill, 'killname': _cmd_killname,
    'tele': _cmd_tele, 'reload': _cmd_reload, 'pick': _cmd_pick, 'turnin': _cmd_turnin,
    'camera': _cmd_camera, 'look': _cmd_look, 'py': _cmd_py,
    'hide': _cmd_hide, 'unhide': _cmd_unhide, 'probe': _cmd_probe, 'dismiss': _cmd_dismiss,
    'zoom': _cmd_zoom, 'ui': _cmd_ui, 'frame': _cmd_frame,
}


def _run(line):
    parts = line.split(None, 1)
    name = parts[0].lower()
    args = ''
    if len(parts) > 1:
        args = parts[1].strip()
    command = COMMANDS.get(name)
    if command is None:
        _say('unknown command: %s' % (line,))
        return
    try:
        _say('%s -> %s' % (line, command(args)))
    except:
        _say('%s failed: %s: %s' % (line, sys.exc_info()[0], sys.exc_info()[1]))


# --- the periodic update --------------------------------------------------------------------

def _read_commands():
    if not os.path.exists(CMD_FILE):
        return
    try:
        f = open(CMD_FILE, 'r')
        try:
            lines = f.readlines()
        finally:
            f.close()
        os.remove(CMD_FILE)
    except:
        _say('could not read %s: %s' % (CMD_FILE, sys.exc_info()[1]))
        return
    if _allowed[0] is False:
        _say('%d commands ignored: the helper is off for this account' % (len(lines),))
        return
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            _queue.append(line)


def _write_state():
    lines = ['time %s' % time.strftime('%Y-%m-%d %H:%M:%S')]
    player = _player()
    if player is None:
        lines.append('player none')
    else:
        lines.append('player %s %s' % (getattr(player, 'entityId', '?'), _name(player)))
        lines.append('position %s' % (_position(player),))
        try:
            lines.append('tracking %s' % (player.GetTrackingMode(),))
        except:
            pass
    target = _target()
    if target:
        entity = _entity(target)
        lines.append('target %s %s %s' % (target, _name(entity), _position(entity)))
    else:
        lines.append('target none')
    window = _window[0]
    if window is not None:
        lines.append('conversation actor %s mission %s' % (_private(window, 'actorId'), _private(window, 'missionId')))
        index = 1
        for key, value in _choices():
            lines.append('choice %d %r' % (index, value))
            index += 1
        index = 1
        for selection, template in _rewards():
            lines.append('reward %d item template %s' % (index, template))
            index += 1
        if _private(window, 'bChooseRewards'):
            lines.append('reward choice: required, picked %s' % (_private(window, 'rewardSelection'),))
    lines.append('helper %s' % ({None: 'waiting for the account level', True: 'on', False: 'off'}[_allowed[0]],))
    lines.append('queue %d' % (len(_queue),))
    # idle: nothing queued, no wait, kill or camera turn going on (an outside program waits for this).
    idle = not _queue and _kill[0] is None and _look[0] is None and time.time() >= _wait_until[0]
    lines.append('idle %d' % (int(idle),))
    try:
        import client.gameui
        lines.append('dialogs %s' % (list(getattr(client.gameui, 'g_messageBoxIds', []) or []),))
    except:
        pass
    lines.append('results:')
    lines.extend(_results)
    try:
        f = open(STATE_FILE + '.tmp', 'w')
        try:
            f.write('\n'.join(lines) + '\n')
        finally:
            f.close()
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        os.rename(STATE_FILE + '.tmp', STATE_FILE)
    except:
        pass


def _check_new_character():
    player = _player()
    if player is None:
        return
    entity_id = getattr(player, 'entityId', None)
    if entity_id is None or entity_id == _manifestation[0]:
        return
    _manifestation[0] = entity_id
    _allowed[0] = None
    _probe_age[0] = 0
    _say('character %s in the world: checking the account level (%s)' % (entity_id, PROBE_COMMAND))
    _chat(PROBE_COMMAND)


def _decide(allowed, why):
    if _allowed[0] is not None or _probe_age[0] is None:
        return
    _allowed[0] = allowed
    _probe_age[0] = None
    if not allowed:
        del _queue[:]
        _say('helper off: %s' % (why,))
        return
    _say('helper on: %s' % (why,))
    import clientmod_data
    if getattr(clientmod_data, 'QUEST_HELPER_GM_MODE', False):
        _gm_mode(True)


def _on_chat_message(eventId, source, msg, *args):
    # UI_DISPLAY_CHAT_MESSAGE: every line the chat window prints, also the server's answers.
    try:
        text = '%s' % (msg,)
    except:
        return
    try:
        _say('chat: %s' % (text.strip()[:200].encode('ascii', 'replace'),))
    except:
        pass
    if _probe_age[0] is None:
        return
    if text.find('No server flags are set.') >= 0 or text.find('Set: ') >= 0:
        _decide(True, 'account level %d' % (REQUIRED_LEVEL,))
    elif text.find('.flag needs account level') >= 0:
        _decide(False, 'needs account level %d: %s' % (REQUIRED_LEVEL, text.strip()))
    elif text.find('Unknown command: .flag') >= 0:
        _decide(False, 'not a GM account')


def _listen():
    # (Re)register the chat listener when the UI event tables have no copy of it: they are made
    # by uieventmanager.Initialize, after client.gameui loads, and made again on a reset.
    import client.ui.uieventmanager as uieventmanager
    handlers = getattr(uieventmanager, 'g_handlersForAny', None)
    if handlers is None:
        return
    if _on_chat_message not in handlers.get(uieventmanager.UI_DISPLAY_CHAT_MESSAGE, []):
        uieventmanager.RegisterHandler(uieventmanager.UI_DISPLAY_CHAT_MESSAGE, None, _on_chat_message)
        _say('listening to chat')


# A map movie of the loading screen (an instance's) that plays this long is stopped.
MOVIE_STOP_MS = 3000
_movie_ms = [0]
_movie_scan_ms = [0]


def _stop_stuck_movie(msec):
    # The loading screen plays the map's movie before it enters the world (wonkavatorwindow.PlayMovie,
    # entered on HandleMovieEnded). Under Wine that movie never ends, so the client never says the load
    # is done and the server drops it after 60 s ("Transfer timed out"). Stop it as Escape would.
    _movie_scan_ms[0] += msec
    if _movie_scan_ms[0] < 1000:
        return
    msec, _movie_scan_ms[0] = _movie_scan_ms[0], 0
    module = sys.modules.get('client.ui.wonkavatorwindow')
    if module is None:
        return
    import gc
    for o in gc.get_objects():
        if getattr(o, '__class__', None) is module.wonkavatorwindow and getattr(o, '_wonkavatorwindow__moviePlaying', False):
            _movie_ms[0] += msec
            if _movie_ms[0] >= MOVIE_STOP_MS:
                _movie_ms[0] = 0
                o.OnCancelMovie(None, None)
                _say('loading screen: stopped the map movie after %d ms (it does not end under Wine)' % MOVIE_STOP_MS)
            return
    _movie_ms[0] = 0


def _update(msec):
    try:
        _since_poll[0] += msec
        _since_state[0] += msec
        if _since_poll[0] >= POLL_MS:
            _stop_stuck_movie(_since_poll[0])
            _since_poll[0] = 0
            _listen()
            _check_new_character()
            _read_commands()
        if _probe_age[0] is not None:
            _probe_age[0] += msec
            if _probe_age[0] >= PROBE_TIMEOUT_MS:
                _decide(False, 'no answer to %s in %d ms' % (PROBE_COMMAND, PROBE_TIMEOUT_MS))
        if _allowed[0] is False:
            del _queue[:]
        busy = _kill_step() or _look_step()
        while _allowed[0] and _queue and not busy and time.time() >= _wait_until[0] and _world_ready():
            _run(_queue.pop(0))
            busy = _kill[0] is not None or _look[0] is not None
        if _since_state[0] >= STATE_MS:
            _since_state[0] = 0
            _write_state()
    except:
        _say('update failed: %s' % (sys.exc_info()[1],))


# --- attaching ------------------------------------------------------------------------------

def attach_gameui(module, log):
    """Register the periodic update with client.gameui (fully loaded)."""
    global _log
    _log = log
    # The chat listener is registered from the update (_listen): the UI event tables do not
    # exist yet when client.gameui loads (uieventmanager.Initialize makes them).
    module.RegisterForUpdate(_update)
    _say('attached: commands from %s, state in %s' % (CMD_FILE, STATE_FILE))


def attach_conversationwindow(module, log):
    """Remember the conversation window when it is shown."""
    global _log
    _log = log
    cls = getattr(module, 'conversationwindow', None)
    real = cls and cls.__dict__.get('Show')
    if real is None:
        _say('conversationwindow.Show not found; conversation commands will not work')
        return

    def Show(self, *args, **kwargs):
        _window[0] = self
        return real(self, *args, **kwargs)

    Show.__name__ = 'Show'
    cls.Show = Show
    _say('conversation window hooked')


# After "reload": put the kept state back (see _KEPT).
_kept = getattr(sys, '_quest_helper_kept', None)
if _kept is not None:
    for _name_kept, _value_kept in _kept.items():
        globals()[_name_kept] = _value_kept
    sys._quest_helper_kept = None
