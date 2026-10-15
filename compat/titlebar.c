// Window-chrome selectors that Roblox's custom titlebar (an IXP experiment) sends to its
// NSWindow, but that Darling's cocotron AppKit lacks. An unrecognized selector is an uncaught
// NSInvalidArgumentException, which closes the client within seconds of launch.
//
// Built as CoreHaptics.framework: RobloxPlayer weak-links CoreHaptics, Darling has none, and
// roblox-mac keeps any DYLD_FRAMEWORK_PATH it inherits. No CoreHaptics symbols are defined, so
// haptics stay unavailable exactly as before. Plain C against the objc runtime; no SDK needed.
// Rebuild with compat/build.sh.

typedef struct objc_class *Class;
typedef struct objc_selector *SEL;
typedef struct objc_object *id;
typedef signed char BOOL;
typedef long NSInteger;
typedef void (*IMP)(void);
typedef struct { double x, y; } NSPoint;
typedef struct { double width, height; } NSSize;
typedef struct { NSPoint origin; NSSize size; } NSRect;

Class objc_getClass(const char *name);
SEL sel_registerName(const char *name);
void *class_getInstanceMethod(Class cls, SEL sel);
BOOL class_addMethod(Class cls, SEL sel, IMP imp, const char *types);
void objc_msgSend_stret(void);
long write(int fd, const void *buf, unsigned long count);

static void say(const char *message)
{
    unsigned long length = 0;
    while (message[length])
        length++;
    write(2, message, length);
}

// The window manager draws the real titlebar, so these only need to remember what was asked.
static BOOL titlebar_transparent;
static NSInteger title_visibility;

static void set_titlebar_transparent(id self, SEL cmd, BOOL value)
{
    // Roblox flips this only when its titlebar mode changes; the log line shows which mode it chose.
    if (value != titlebar_transparent)
        say(value ? "compat: Roblox switched to its custom titlebar\n" : "compat: Roblox switched to the standard titlebar\n");
    titlebar_transparent = value;
}
static BOOL get_titlebar_transparent(id self, SEL cmd) { return titlebar_transparent; }
static void set_title_visibility(id self, SEL cmd, NSInteger value) { title_visibility = value; }
static NSInteger get_title_visibility(id self, SEL cmd) { return title_visibility; }
// The window manager's titlebar moves the window.
static void perform_window_drag(id self, SEL cmd, id event) {}
// Window coordinates are screen coordinates relative to the frame's origin (both bottom-left).
static NSRect window_frame(id self)
{
    static SEL frame;
    if (!frame)
        frame = sel_registerName("frame");
    return ((NSRect (*)(id, SEL))objc_msgSend_stret)(self, frame);
}
static NSPoint point_from_screen(id self, SEL cmd, NSPoint p)
{
    NSRect f = window_frame(self);
    return (NSPoint){p.x - f.origin.x, p.y - f.origin.y};
}
static NSPoint point_to_screen(id self, SEL cmd, NSPoint p)
{
    NSRect f = window_frame(self);
    return (NSPoint){p.x + f.origin.x, p.y + f.origin.y};
}
static NSRect rect_from_screen(id self, SEL cmd, NSRect r)
{
    r.origin = point_from_screen(self, cmd, r.origin);
    return r;
}
static NSRect rect_to_screen(id self, SEL cmd, NSRect r)
{
    r.origin = point_to_screen(self, cmd, r.origin);
    return r;
}
// nil reads as "no particular appearance"; callers fall back to their defaults.
static id effective_appearance(id self, SEL cmd) { return 0; }

// With CustomTitleBarM1Enabled set, Roblox draws a second, Mac-style title strip inside the
// window. Local FFlags.json overrides for it are ignored, and server settings or experiment
// assignments can set it at any time, so a thread holds the flag's byte at 0. The byte is found
// through the code that registers the flag (lea rdi, "name"; lea rsi, flag; mov edx, 1), so no
// addresses are hard-coded; if that pattern is not found exactly once, nothing is touched.

struct mach_header_64 { unsigned magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved; };
struct segment_command_64 { unsigned cmd, cmdsize; char segname[16]; unsigned long vmaddr, vmsize, fileoff, filesize; int maxprot, initprot; unsigned nsects, flags; };
struct section_64 { char sectname[16], segname[16]; unsigned long addr, size; unsigned offset, align, reloff, nreloc, flags, reserved1, reserved2, reserved3; };

const struct mach_header_64 *_dyld_get_image_header(unsigned image_index);
long _dyld_get_image_vmaddr_slide(unsigned image_index);
int pthread_create(void *thread, const void *attr, void *(*start)(void *), void *arg);
int usleep(unsigned microseconds);

static const char FLAG_NAME[] = "CustomTitleBarM1Enabled";

static int same(const char *a, const char *b, unsigned long n)
{
    while (n--)
        if (*a++ != *b++)
            return 0;
    return 1;
}

static const struct section_64 *find_section(const struct mach_header_64 *header, const char *name)
{
    // Compare through the name's terminator; section names shorter than 16 bytes are NUL-padded.
    unsigned long length = 0;
    while (name[length++])
        ;
    const char *command = (const char *)(header + 1);
    for (unsigned i = 0; i < header->ncmds; i++) {
        const struct segment_command_64 *segment = (const void *)command;
        if (segment->cmd == 0x19 && same(segment->segname, "__TEXT", 7)) {
            const struct section_64 *section = (const void *)(segment + 1);
            for (unsigned j = 0; j < segment->nsects; j++, section++)
                if (same(section->sectname, name, length))
                    return section;
        }
        command += segment->cmdsize;
    }
    return 0;
}

static int rip_target(const unsigned char *instruction, unsigned length, const unsigned char *target)
{
    int displacement;
    __builtin_memcpy(&displacement, instruction + length - 4, 4);
    return instruction + length + displacement == target;
}

static volatile unsigned char *find_flag(void)
{
    const struct mach_header_64 *header = _dyld_get_image_header(0);
    long slide = _dyld_get_image_vmaddr_slide(0);
    if (!header || header->magic != 0xfeedfacf)
        return 0;
    const struct section_64 *strings = find_section(header, "__cstring");
    const struct section_64 *text = find_section(header, "__text");
    if (!strings || !text)
        return 0;
    const unsigned char *name = 0, *s = (const void *)(strings->addr + slide);
    for (unsigned long i = 1; i + sizeof FLAG_NAME <= strings->size; i++)
        if (!s[i - 1] && same((const char *)s + i, FLAG_NAME, sizeof FLAG_NAME)) {
            name = s + i;
            break;
        }
    if (!name)
        return 0;
    const unsigned char *code = (const void *)(text->addr + slide), *flag = 0;
    for (unsigned long i = 0; i + 19 <= text->size; i++) {
        const unsigned char *c = code + i;
        if (c[0] == 0x48 && c[1] == 0x8d && c[2] == 0x3d && rip_target(c, 7, name) &&
            c[7] == 0x48 && c[8] == 0x8d && c[9] == 0x35 &&
            c[14] == 0xba && c[15] == 1 && !c[16] && !c[17] && !c[18]) {
            int displacement;
            __builtin_memcpy(&displacement, c + 10, 4);
            if (flag)
                return 0;
            flag = c + 14 + displacement;
        }
    }
    return (volatile unsigned char *)flag;
}

static void *hold_flag_off(void *unused)
{
    volatile unsigned char *flag = find_flag();
    if (!flag) {
        say("compat: CustomTitleBarM1Enabled not found; leaving Roblox's titlebar setting alone\n");
        return 0;
    }
    say("compat: holding CustomTitleBarM1Enabled off\n");
    // Settings arrive during startup; poll tightly then, and lightly afterwards.
    for (unsigned i = 0;; i++) {
        if (*flag)
            *flag = 0;
        usleep(i < 30000 ? 1000 : 100000);
    }
}

static void add(const char *class_name, const char *selector, IMP imp, const char *types)
{
    Class cls = objc_getClass(class_name);
    SEL sel = sel_registerName(selector);
    // Never replace a real implementation, including one inherited from a superclass.
    if (cls && !class_getInstanceMethod(cls, sel))
        class_addMethod(cls, sel, imp, types);
}

__attribute__((constructor)) static void install(void)
{
    add("NSWindow", "setTitlebarAppearsTransparent:", (IMP)set_titlebar_transparent, "v@:c");
    add("NSWindow", "titlebarAppearsTransparent", (IMP)get_titlebar_transparent, "c@:");
    add("NSWindow", "setTitleVisibility:", (IMP)set_title_visibility, "v@:q");
    add("NSWindow", "titleVisibility", (IMP)get_title_visibility, "q@:");
    add("NSWindow", "performWindowDragWithEvent:", (IMP)perform_window_drag, "v@:@");
    add("NSWindow", "convertPointFromScreen:", (IMP)point_from_screen, "{CGPoint=dd}@:{CGPoint=dd}");
    add("NSWindow", "convertPointToScreen:", (IMP)point_to_screen, "{CGPoint=dd}@:{CGPoint=dd}");
    add("NSWindow", "convertRectFromScreen:", (IMP)rect_from_screen, "{CGRect={CGPoint=dd}{CGSize=dd}}@:{CGRect={CGPoint=dd}{CGSize=dd}}");
    add("NSWindow", "convertRectToScreen:", (IMP)rect_to_screen, "{CGRect={CGPoint=dd}{CGSize=dd}}@:{CGRect={CGPoint=dd}{CGSize=dd}}");
    add("NSWindow", "effectiveAppearance", (IMP)effective_appearance, "@@:");
    add("NSView", "effectiveAppearance", (IMP)effective_appearance, "@@:");
    add("NSApplication", "effectiveAppearance", (IMP)effective_appearance, "@@:");
    unsigned long thread;
    pthread_create(&thread, 0, hold_flag_off, 0);
}
