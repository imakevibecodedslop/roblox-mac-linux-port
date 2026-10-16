// Force-included when building the UI helper (c++ -include tools/glibc-baseline.h).
// glibc 2.43 added new symbol versions of these math functions, so a helper built on a newer system
// would refuse to load on the AppImage's baseline (glibc 2.39). Bind the original x86-64 versions.
__asm__(".symver acosf,acosf@GLIBC_2.2.5");
__asm__(".symver atan2f,atan2f@GLIBC_2.2.5");
__asm__(".symver sqrtf,sqrtf@GLIBC_2.2.5");
