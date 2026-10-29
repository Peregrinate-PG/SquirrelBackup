// Test-only interposition for disposable Squirrel Backup child processes.
// Mach-O interposition ABI reference: Apple's dyld include/mach-o/dyld-interposing.h.
// No changes are made to the production executable or any system setting.
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <unistd.h>

static unsigned fired;
static bool selected(const char* path, const char* operation) {
  const char* root = getenv("SQUIRREL_FAULT_ROOT");
  const char* mode = getenv("SQUIRREL_FAULT_OP");
  const char* suffix = getenv("SQUIRREL_FAULT_SUFFIX");
  if (!root || !mode || !suffix || strcmp(mode, operation)) {
    return false;
  }
  const size_t a = strlen(path), b = strlen(suffix), n = strlen(root);
  return a > n && !strncmp(path, root, n) && path[n] == '/' && a >= b &&
         !strcmp(path + a - b, suffix);
}
static bool descriptor(int fd, const char* operation) {
  char path[MAXPATHLEN];
  return fcntl(fd, F_GETPATH, path) == 0 && selected(path, operation);
}
static void event(const char* operation, int error) {
  ++fired;
  if (fired == 1) {
    dprintf(STDERR_FILENO, "[fault] %s errno=%d\n", operation, error);
  }
  errno = error;
}
static ssize_t failed_write(int fd, const void* data, size_t count) {
  if (descriptor(fd, "write-enospc")) {
    event("write-enospc", ENOSPC);
    return -1;
  }
  if (!fired && descriptor(fd, "write-eintr")) {
    event("write-eintr", EINTR);
    return -1;
  }
  if (descriptor(fd, "write-short")) {
    event("write-short", 0);
    return write(fd, data, count > 4096 ? 4096 : count);
  }
  return write(fd, data, count);
}
static size_t failed_fwrite(const void* data, size_t size, size_t count, FILE* stream) {
  if (descriptor(fileno(stream), "fwrite-enospc")) {
    event("fwrite-enospc", ENOSPC);
    return 0;
  }
  return fwrite(data, size, count, stream);
}
static int failed_fsync(int fd) {
  if (descriptor(fd, "fsync-eio")) {
    event("fsync-eio", EIO);
    return -1;
  }
  return fsync(fd);
}
static int failed_link(const char* source, const char* destination) {
  if (selected(destination, "link-eacces")) {
    event("link-eacces", EACCES);
    return -1;
  }
  return link(source, destination);
}
static int failed_rename(const char* source, const char* destination, unsigned flags) {
  if (selected(destination, "rename-eio")) {
    event("rename-eio", EIO);
    return -1;
  }
  return renamex_np(source, destination, flags);
}
static int failed_chmod(const char* path, mode_t mode) {
  if (selected(path, "chmod-eperm")) {
    event("chmod-eperm", EPERM);
    return -1;
  }
  return chmod(path, mode);
}
// The section stores replacement/original address pairs consumed by dyld.
struct hook_pair {
  const void* replacement;
  const void* original;
};
__attribute__((used, section("__DATA,__interpose"))) static const struct hook_pair hooks[] = {
    {(const void*)failed_write, (const void*)write},
    {(const void*)failed_fwrite, (const void*)fwrite},
    {(const void*)failed_fsync, (const void*)fsync},
    {(const void*)failed_link, (const void*)link},
    {(const void*)failed_rename, (const void*)renamex_np},
    {(const void*)failed_chmod, (const void*)chmod}};
