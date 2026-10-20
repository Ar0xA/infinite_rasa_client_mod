/*
 * clientmod_native.pyd: proof that the client mod can run native code in the game process.
 *
 * Python 2.4 imports this DLL as the module clientmod_native (clientbootstrap.py, in a
 * try/except). On import it:
 *   - writes a line to client_mod.log with the process id, the exe path and the Wine
 *     version (ntdll.wine_get_version, absent on real Windows);
 *   - starts a thread that adds " [Infinite Rasa mod]" to the game window title (checked
 *     every 2 seconds, as the game may set its title again), so the result shows in the
 *     title bar and the task bar.
 * Python gets one function: clientmod_native.info() -> str.
 *
 * No Python headers or import library: the few Python C API functions are looked up in
 * python24.dll at run time. Only kernel32 and user32 are used, no C runtime calls.
 * Build: native/build.sh (32-bit x86, like tabula_rasa.exe and python24.dll).
 */
#include <windows.h>

#define LOG_NAME "client_mod.log"
#define TITLE_TAG " [Infinite Rasa mod]"
#define PYTHON_API_VERSION 1012 /* Python 2.4 */
#define METH_NOARGS 0x0004

typedef void PyObject;
typedef PyObject *(*PyCFunction)(PyObject *, PyObject *);
typedef struct {
    const char *ml_name;
    PyCFunction ml_meth;
    int ml_flags;
    const char *ml_doc;
} PyMethodDef;

typedef PyObject *(*Py_InitModule4_t)(const char *, PyMethodDef *, const char *, PyObject *, int);
typedef PyObject *(*PyString_FromString_t)(const char *);

static PyString_FromString_t pPyString_FromString;
static char g_info[512];

static void log_line(const char *text)
{
    char line[768];
    SYSTEMTIME t;
    DWORD written;
    HANDLE f = CreateFileA(LOG_NAME, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                           NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE)
        return;
    GetLocalTime(&t);
    wsprintfA(line, "%04d-%02d-%02d %02d:%02d:%02d native: %s\r\n", t.wYear, t.wMonth, t.wDay,
              t.wHour, t.wMinute, t.wSecond, text);
    WriteFile(f, line, lstrlenA(line), &written, NULL);
    CloseHandle(f);
}

static const char *wine_version(void)
{
    typedef const char *(*wine_get_version_t)(void);
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    wine_get_version_t get = ntdll ? (wine_get_version_t)GetProcAddress(ntdll, "wine_get_version") : NULL;
    return get ? get() : "none (not Wine)";
}

static int g_title_sets = 0;

/* Add TITLE_TAG to a visible top-level window of this process whose title lacks it. */
static BOOL CALLBACK tag_window(HWND hwnd, LPARAM unused)
{
    char title[512], message[640];
    DWORD pid = 0;
    int n;
    (void)unused;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(hwnd) || GetWindow(hwnd, GW_OWNER) != NULL)
        return TRUE;
    n = GetWindowTextA(hwnd, title, sizeof(title) - sizeof(TITLE_TAG));
    if (n <= 0)
        return TRUE;
    if (n >= (int)sizeof(TITLE_TAG) - 1 && lstrcmpA(title + n - (sizeof(TITLE_TAG) - 1), TITLE_TAG) == 0)
        return TRUE;
    lstrcatA(title, TITLE_TAG);
    SetWindowTextA(hwnd, title);
    if (g_title_sets++ < 10) {
        wsprintfA(message, "window %p title set to \"%s\"", (void *)hwnd, title);
        log_line(message);
    }
    return TRUE;
}

/* The game may create its window late or set its title again: check every 2 seconds. */
static DWORD WINAPI title_thread(LPVOID unused)
{
    (void)unused;
    for (;;) {
        EnumWindows(tag_window, 0);
        Sleep(2000);
    }
    return 0;
}

static PyObject *native_info(PyObject *self, PyObject *args)
{
    (void)self;
    (void)args;
    return pPyString_FromString(g_info);
}

static PyMethodDef methods[] = {
    {"info", native_info, METH_NOARGS, "Process id, exe path and Wine version, as one string."},
    {NULL, NULL, 0, NULL},
};

__declspec(dllexport) void initclientmod_native(void)
{
    char exe[MAX_PATH];
    HANDLE thread;
    HMODULE python = GetModuleHandleA("python24.dll");
    Py_InitModule4_t pPy_InitModule4;

    if (python == NULL) {
        log_line("python24.dll is not loaded; module not set up");
        return;
    }
    pPy_InitModule4 = (Py_InitModule4_t)GetProcAddress(python, "Py_InitModule4");
    pPyString_FromString = (PyString_FromString_t)GetProcAddress(python, "PyString_FromString");
    if (pPy_InitModule4 == NULL || pPyString_FromString == NULL) {
        log_line("Python C API functions not found in python24.dll");
        return;
    }

    exe[0] = 0;
    GetModuleFileNameA(NULL, exe, sizeof(exe));
    wsprintfA(g_info, "pid %lu, exe %s, Wine %s", GetCurrentProcessId(), exe, wine_version());
    log_line(g_info);

    thread = CreateThread(NULL, 0, title_thread, NULL, 0, NULL);
    if (thread != NULL)
        CloseHandle(thread);

    pPy_InitModule4("clientmod_native", methods, "Infinite Rasa client mod: native code proof.",
                    NULL, PYTHON_API_VERSION);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH)
        DisableThreadLibraryCalls(instance);
    return TRUE;
}
