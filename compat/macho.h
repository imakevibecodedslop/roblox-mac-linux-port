// Mach-O helpers shared by the compat sources: logging, loaded-image lookup, and sections and
// symbols of an image as mapped in memory. Plain C with local declarations; no SDK needed.
#pragma once

struct mach_header_64 { unsigned magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved; };
struct load_command { unsigned cmd, cmdsize; };
struct segment_command_64 { unsigned cmd, cmdsize; char segname[16]; unsigned long vmaddr, vmsize, fileoff, filesize; int maxprot, initprot; unsigned nsects, flags; };
struct section_64 { char sectname[16], segname[16]; unsigned long addr, size; unsigned offset, align, reloff, nreloc, flags, reserved1, reserved2, reserved3; };
struct symtab_command { unsigned cmd, cmdsize, symoff, nsyms, stroff, strsize; };
struct nlist_64 { unsigned strx; unsigned char type, sect; unsigned short desc; unsigned long value; };

#define LC_SYMTAB 0x2
#define LC_SEGMENT_64 0x19
#define N_TYPE 0x0e
#define N_SECT 0x0e

long write(int fd, const void *buf, unsigned long count);
const struct mach_header_64 *_dyld_get_image_header(unsigned image_index);
long _dyld_get_image_vmaddr_slide(unsigned image_index);

static inline void say(const char *message)
{
    unsigned long length = 0;
    while (message[length])
        length++;
    write(2, message, length);
}

static inline int same(const char *a, const char *b, unsigned long n)
{
    while (n--)
        if (*a++ != *b++)
            return 0;
    return 1;
}

static inline const struct segment_command_64 *find_segment(const struct mach_header_64 *header, const char *name)
{
    unsigned long length = 0;
    while (name[length++])
        ;
    const char *command = (const char *)(header + 1);
    for (unsigned i = 0; i < header->ncmds; i++) {
        const struct segment_command_64 *segment = (const void *)command;
        if (segment->cmd == LC_SEGMENT_64 && same(segment->segname, name, length))
            return segment;
        command += segment->cmdsize;
    }
    return 0;
}

static inline const struct section_64 *find_section(const struct mach_header_64 *header, const char *name)
{
    // Compare through the name's terminator; section names shorter than 16 bytes are NUL-padded.
    unsigned long length = 0;
    while (name[length++])
        ;
    const struct segment_command_64 *text = find_segment(header, "__TEXT");
    const struct section_64 *section = text ? (const void *)(text + 1) : 0;
    for (unsigned j = 0; text && j < text->nsects; j++, section++)
        if (same(section->sectname, name, length))
            return section;
    return 0;
}

// Address of a symbol defined in the image, including private ones dlsym cannot see.
static inline void *find_symbol(const struct mach_header_64 *header, long slide, const char *name)
{
    const struct segment_command_64 *linkedit = find_segment(header, "__LINKEDIT");
    const struct symtab_command *symtab = 0;
    const char *command = (const char *)(header + 1);
    for (unsigned i = 0; i < header->ncmds; i++) {
        if (((const struct load_command *)command)->cmd == LC_SYMTAB)
            symtab = (const void *)command;
        command += ((const struct load_command *)command)->cmdsize;
    }
    if (!linkedit || !symtab)
        return 0;
    // Symbol and string tables are given as file offsets inside __LINKEDIT.
    const char *base = (const char *)(linkedit->vmaddr + slide - linkedit->fileoff);
    const struct nlist_64 *symbols = (const void *)(base + symtab->symoff);
    const char *strings = base + symtab->stroff;
    unsigned long length = 0;
    while (name[length++])
        ;
    for (unsigned i = 0; i < symtab->nsyms; i++)
        if ((symbols[i].type & N_TYPE) == N_SECT && symbols[i].strx < symtab->strsize &&
            same(strings + symbols[i].strx, name, length))
            return (void *)(symbols[i].value + slide);
    return 0;
}
