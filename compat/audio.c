// Darling's AudioToolbox crashes when Roblox stops an audio unit that has already been disposed.
//
// AudioOutputUnitStop, AudioOutputUnitStart, AudioUnitInitialize and AudioUnitUninitialize all
// go through dispatchCall<>(ComponentInstanceRecord*, short) (darling/src/CoreAudio/AudioToolbox/
// ComponentDispatch.h). It looks the handle up with AudioComponentManager::instanceInterface()
// and calls Lookup() on the result without checking it, so a disposed handle dereferences null.
// macOS returns badComponentInstance for such a handle; this replaces that dispatchCall
// instantiation with one that does the same.
//
// dispatchCall and the manager methods are private symbols, found through AudioToolbox's symbol
// table. The function is replaced only when its first bytes match the build this was written for.

#include "macho.h"

#define badComponentInstance ((int)0x80008001)
#define badComponentSelector ((int)0x80008002)

int mprotect(void *addr, unsigned long len, int prot);
void *dlsym(void *handle, const char *symbol);
unsigned _dyld_image_count(void);
const char *_dyld_get_image_name(unsigned image_index);
#define RTLD_DEFAULT ((void *)-2)
#define PROT_READ 1
#define PROT_WRITE 2
#define PROT_EXEC 4

typedef struct {
    void *open, *close;
    int (*(*lookup)(short selector))(void *self, ...);
    void *reserved;
} PlugInInterface;

typedef struct {
    unsigned char flags, paramSize;
    short what;
    long params[1];
} ComponentParameters;

static void *(*manager_instance)(void);
static PlugInInterface *(*instance_interface)(void *manager, void *instance);

static int dispatch_without_arguments(void *instance, short selector)
{
    // Darling marks its own instances by setting bit 31 of the handle (AudioComponentManager::isOurInstance).
    if ((unsigned)(unsigned long)instance & 0x80000000u) {
        PlugInInterface *interface = instance_interface(manager_instance(), instance);
        if (!interface) {
            say("compat: ignored a call on a closed audio unit\n");
            return badComponentInstance;
        }
        int (*method)(void *self, ...) = interface->lookup(selector);
        return method ? method(interface) : badComponentSelector;
    }
    // Carbon components, as in ComponentDispatch.h for LP64.
    static int (*call_component_dispatch)(ComponentParameters *);
    if (!call_component_dispatch)
        *(void **)&call_component_dispatch = dlsym(RTLD_DEFAULT, "CallComponentDispatch");
    ComponentParameters parameters = {0, sizeof(long), selector, {(long)instance}};
    return call_component_dispatch ? call_component_dispatch(&parameters) : badComponentSelector;
}

static const struct mach_header_64 *find_image(const char *suffix, long *slide)
{
    unsigned long suffix_length = 0;
    while (suffix[suffix_length])
        suffix_length++;
    for (unsigned i = 0; i < _dyld_image_count(); i++) {
        const char *name = _dyld_get_image_name(i);
        unsigned long length = 0;
        while (name && name[length])
            length++;
        if (length >= suffix_length && same(name + length - suffix_length, suffix, suffix_length)) {
            *slide = _dyld_get_image_vmaddr_slide(i);
            return _dyld_get_image_header(i);
        }
    }
    return 0;
}

// Replace the start of `function` with `movabs rax, target; jmp rax`.
static int redirect(unsigned char *function, void *target)
{
    unsigned long page = (unsigned long)function & ~0xfffUL;
    unsigned long span = (unsigned long)function + 12 - page;
    if (mprotect((void *)page, span, PROT_READ | PROT_WRITE | PROT_EXEC))
        return 0;
    unsigned long address = (unsigned long)target;
    function[0] = 0x48;
    function[1] = 0xb8;
    __builtin_memcpy(function + 2, &address, 8);
    function[10] = 0xff;
    function[11] = 0xe0;
    mprotect((void *)page, span, PROT_READ | PROT_EXEC);
    return 1;
}

__attribute__((constructor)) static void guard_audio_units(void)
{
    // push rbp; mov rbp,rsp; push r14; push rbx; sub rsp,0x10; mov ebx,esi; mov r14,rdi
    static const unsigned char expected[16] = {0x55, 0x48, 0x89, 0xe5, 0x41, 0x56, 0x53, 0x48,
                                               0x83, 0xec, 0x10, 0x89, 0xf3, 0x49, 0x89, 0xfe};
    long slide;
    const struct mach_header_64 *image = find_image("/AudioToolbox.framework/Versions/A/AudioToolbox", &slide);
    if (!image)
        return;
    unsigned char *dispatch = find_symbol(image, slide, "__Z12dispatchCallIJEEiP23ComponentInstanceRecordsDpT_");
    *(void **)&manager_instance = find_symbol(image, slide, "__ZN21AudioComponentManager8instanceEv");
    *(void **)&instance_interface = find_symbol(image, slide,
        "__ZN21AudioComponentManager17instanceInterfaceEP23ComponentInstanceRecord");
    if (!dispatch || !manager_instance || !instance_interface || !same((const char *)dispatch, (const char *)expected, 16)) {
        say("compat: AudioToolbox differs from the expected build; closed audio units are not guarded\n");
        return;
    }
    if (!redirect(dispatch, (void *)dispatch_without_arguments))
        say("compat: could not guard AudioToolbox against closed audio units\n");
}
