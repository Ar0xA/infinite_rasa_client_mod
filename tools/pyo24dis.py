"""Disassemble Python 2.4 .pyo files from the Tabula Rasa client (trpython.zip / game.zip).

usage:
  pyo24dis.py <archive.zip> <member.pyo> [name ...]   disassemble the module, or only the
                                                      functions/classes/methods named
                                                      (e.g. BuildMissionNameText, Class.method)
  pyo24dis.py <archive.zip> --grep <word>             list members whose names or strings
                                                      contain <word>
Runs on Python 3. Reads the archive only; nothing is imported or executed.
"""
import struct
import sys
import zipfile

HAVE_ARGUMENT = 90
OPNAMES = {
    0: 'STOP_CODE', 1: 'POP_TOP', 2: 'ROT_TWO', 3: 'ROT_THREE', 4: 'DUP_TOP', 5: 'ROT_FOUR', 9: 'NOP',
    10: 'UNARY_POSITIVE', 11: 'UNARY_NEGATIVE', 12: 'UNARY_NOT', 13: 'UNARY_CONVERT', 15: 'UNARY_INVERT',
    18: 'LIST_APPEND', 19: 'BINARY_POWER', 20: 'BINARY_MULTIPLY', 21: 'BINARY_DIVIDE', 22: 'BINARY_MODULO',
    23: 'BINARY_ADD', 24: 'BINARY_SUBTRACT', 25: 'BINARY_SUBSCR', 26: 'BINARY_FLOOR_DIVIDE',
    27: 'BINARY_TRUE_DIVIDE', 28: 'INPLACE_FLOOR_DIVIDE', 29: 'INPLACE_TRUE_DIVIDE',
    30: 'SLICE+0', 31: 'SLICE+1', 32: 'SLICE+2', 33: 'SLICE+3',
    40: 'STORE_SLICE+0', 41: 'STORE_SLICE+1', 42: 'STORE_SLICE+2', 43: 'STORE_SLICE+3',
    50: 'DELETE_SLICE+0', 51: 'DELETE_SLICE+1', 52: 'DELETE_SLICE+2', 53: 'DELETE_SLICE+3',
    55: 'INPLACE_ADD', 56: 'INPLACE_SUBTRACT', 57: 'INPLACE_MULTIPLY', 58: 'INPLACE_DIVIDE',
    59: 'INPLACE_MODULO', 60: 'STORE_SUBSCR', 61: 'DELETE_SUBSCR', 62: 'BINARY_LSHIFT', 63: 'BINARY_RSHIFT',
    64: 'BINARY_AND', 65: 'BINARY_XOR', 66: 'BINARY_OR', 67: 'INPLACE_POWER', 68: 'GET_ITER',
    70: 'PRINT_EXPR', 71: 'PRINT_ITEM', 72: 'PRINT_NEWLINE', 73: 'PRINT_ITEM_TO', 74: 'PRINT_NEWLINE_TO',
    75: 'INPLACE_LSHIFT', 76: 'INPLACE_RSHIFT', 77: 'INPLACE_AND', 78: 'INPLACE_XOR', 79: 'INPLACE_OR',
    80: 'BREAK_LOOP', 82: 'LOAD_LOCALS', 83: 'RETURN_VALUE', 84: 'IMPORT_STAR', 85: 'EXEC_STMT',
    86: 'YIELD_VALUE', 87: 'POP_BLOCK', 88: 'END_FINALLY', 89: 'BUILD_CLASS',
    90: 'STORE_NAME', 91: 'DELETE_NAME', 92: 'UNPACK_SEQUENCE', 93: 'FOR_ITER', 95: 'STORE_ATTR',
    96: 'DELETE_ATTR', 97: 'STORE_GLOBAL', 98: 'DELETE_GLOBAL', 99: 'DUP_TOPX', 100: 'LOAD_CONST',
    101: 'LOAD_NAME', 102: 'BUILD_TUPLE', 103: 'BUILD_LIST', 104: 'BUILD_MAP', 105: 'LOAD_ATTR',
    106: 'COMPARE_OP', 107: 'IMPORT_NAME', 108: 'IMPORT_FROM', 110: 'JUMP_FORWARD', 111: 'JUMP_IF_FALSE',
    112: 'JUMP_IF_TRUE', 113: 'JUMP_ABSOLUTE', 116: 'LOAD_GLOBAL', 119: 'CONTINUE_LOOP', 120: 'SETUP_LOOP',
    121: 'SETUP_EXCEPT', 122: 'SETUP_FINALLY', 124: 'LOAD_FAST', 125: 'STORE_FAST', 126: 'DELETE_FAST',
    130: 'RAISE_VARARGS', 131: 'CALL_FUNCTION', 132: 'MAKE_FUNCTION', 133: 'BUILD_SLICE',
    134: 'MAKE_CLOSURE', 135: 'LOAD_CLOSURE', 136: 'LOAD_DEREF', 137: 'STORE_DEREF',
    140: 'CALL_FUNCTION_VAR', 141: 'CALL_FUNCTION_KW', 142: 'CALL_FUNCTION_VAR_KW', 143: 'EXTENDED_ARG',
}
COMPARE = ('<', '<=', '==', '!=', '>', '>=', 'in', 'not in', 'is', 'is not', 'exception match', 'BAD')
JREL = (93, 110, 111, 112, 120, 121, 122)
JABS = (113, 119)


class Code(object):
    pass


class Reader(object):
    def __init__(self, data):
        self.b = data
        self.p = 0
        self.interned = []

    def take(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def i32(self):
        return struct.unpack('<i', self.take(4))[0]

    def text(self, raw):
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return raw.decode('latin-1')

    def obj(self):
        t = chr(self.take(1)[0])
        if t in '0N':
            return None
        if t == 'F':
            return False
        if t == 'T':
            return True
        if t == 'S':
            return StopIteration
        if t == '.':
            return Ellipsis
        if t == 'i':
            return self.i32()
        if t == 'I':
            return struct.unpack('<q', self.take(8))[0]
        if t == 'l':
            n = self.i32()
            v = 0
            for k in range(abs(n)):
                v |= struct.unpack('<H', self.take(2))[0] << (15 * k)
            return -v if n < 0 else v
        if t == 'f':
            return float(self.take(self.take(1)[0]))
        if t == 'g':
            return struct.unpack('<d', self.take(8))[0]
        if t == 's':
            return self.take(self.i32())  # bytes: code strings and byte strings
        if t == 't':
            v = self.text(self.take(self.i32()))
            self.interned.append(v)
            return v
        if t == 'R':
            return self.interned[self.i32()]
        if t == 'u':
            return self.take(self.i32()).decode('utf-8', 'replace')
        if t == '(':
            return tuple(self.obj() for _ in range(self.i32()))
        if t == '[':
            return [self.obj() for _ in range(self.i32())]
        if t == '{':
            d = {}
            while True:
                if self.b[self.p:self.p + 1] == b'0':
                    self.p += 1
                    break
                k = self.obj()
                d[k] = self.obj()
            return d
        if t == 'c':
            c = Code()
            c.argcount, c.nlocals, c.stacksize, c.flags = [self.i32() for _ in range(4)]
            c.code = self.obj()
            c.consts = self.obj()
            c.names = self.obj()
            c.varnames = self.obj()
            c.freevars = self.obj()
            c.cellvars = self.obj()
            c.filename = self.obj()
            c.name = self.obj()
            c.firstlineno = self.i32()
            c.lnotab = self.obj()
            return c
        raise ValueError('bad marshal type %r at %d' % (t, self.p))


def load(archive, member):
    data = zipfile.ZipFile(archive).read(member)
    return Reader(data[8:]).obj()


def show(v):
    if isinstance(v, Code):
        return '<code %s>' % v.name
    if isinstance(v, bytes):
        try:
            return repr(v.decode('ascii'))
        except UnicodeDecodeError:
            return repr(v)
    return repr(v)


def dis(co, indent=''):
    code = co.code
    cells = tuple(co.cellvars or ()) + tuple(co.freevars or ())
    i, ext = 0, 0
    print('%s== %s (args %d: %s)' % (indent, co.name, co.argcount, ', '.join(co.varnames[:co.argcount])))
    while i < len(code):
        op = code[i]
        name = OPNAMES.get(op, 'OP_%d' % op)
        if op >= HAVE_ARGUMENT:
            arg = code[i + 1] | (code[i + 2] << 8) | ext
            ext = 0
            here = i
            i += 3
            if op == 143:
                ext = arg << 16
                continue
            if op == 100:
                note = show(co.consts[arg])
            elif op in (90, 91, 95, 96, 97, 98, 101, 105, 107, 108, 116):
                note = co.names[arg]
            elif op in (124, 125, 126):
                note = co.varnames[arg]
            elif op in (135, 136, 137):
                note = cells[arg] if arg < len(cells) else arg
            elif op == 106:
                note = COMPARE[arg]
            elif op in JREL:
                note = 'to %d' % (i + arg)
            elif op in JABS:
                note = 'to %d' % arg
            else:
                note = arg
            print('%s%5d %-20s %s' % (indent, here, name, note))
        else:
            print('%s%5d %s' % (indent, i, name))
            i += 1


def walk(co, path=''):
    """Yield (dotted name, code) for every nested code object."""
    for c in co.consts or ():
        if isinstance(c, Code):
            full = (path + '.' if path else '') + c.name
            yield full, c
            for x in walk(c, full):
                yield x


def strings(co):
    for c in co.consts or ():
        if isinstance(c, Code):
            for s in strings(c):
                yield s
        elif isinstance(c, (str, bytes)):
            yield c if isinstance(c, str) else c.decode('latin-1')
    for n in tuple(co.names or ()) + tuple(co.varnames or ()):
        yield n


def main(argv):
    archive = argv[1]
    if argv[2] == '--grep':
        word = argv[3].lower()
        z = zipfile.ZipFile(archive)
        for member in z.namelist():
            if not member.endswith('.pyo'):
                continue
            hit = word in member.lower()
            if not hit:
                try:
                    co = Reader(z.read(member)[8:]).obj()
                    hit = any(word in s.lower() for s in strings(co))
                except Exception:
                    hit = False
            if hit:
                print(member)
        return
    co = load(archive, argv[2])
    wanted = argv[3:]
    if not wanted:
        dis(co)
        for full, c in walk(co):
            print()
            dis(c, '')
        return
    for full, c in walk(co):
        if full in wanted or full.split('.')[-1] in wanted:
            print('# %s' % full)
            dis(c)
            print()


if __name__ == '__main__':
    main(sys.argv)
