// Copyright 2026 Squirrel Backup course project.
#ifndef SQUIRREL_INTERNAL_H_
#define SQUIRREL_INTERNAL_H_
#include <fcntl.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "squirrel/backup.h"

namespace squirrel {

constexpr uint64_t kMaxFileSize = uint64_t{1} << 40;
constexpr size_t kMaxEntries = 1000000;
constexpr size_t kMaxTextSize = 65536;
constexpr size_t kMaxAttributeCount = 4096;
constexpr size_t kMaxAttributeBytes = 64 * 1024 * 1024;

inline void require(bool ok, const std::string& message) {
  if (!ok) {
    throw Error(message);
  }
}

inline void syscheck(bool ok, const std::string& message) {
  if (!ok) {
    throw Error(message + ": " + std::strerror(errno));
  }
}

inline void emit(const Log& log, const std::string& message) {
  if (log) {
    log(message);
  }
}

struct Fd {
  int value;
  explicit Fd(int fd) : value(fd) {}
  ~Fd() {
    if (value >= 0) {
      ::close(value);
    }
  }
  Fd(const Fd&) = delete;
  Fd& operator=(const Fd&) = delete;
};
struct TempDir {
  fs::path path;
  explicit TempDir(const fs::path& parent = fs::temp_directory_path()) {
    std::string pattern = (parent / ".squirrel-XXXXXX").string();
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back(0);
    char* result = ::mkdtemp(buffer.data());
    syscheck(result != nullptr, "Cannot create private temporary directory");
    path = result;
  }
  TempDir(const TempDir&) = delete;
  TempDir& operator=(const TempDir&) = delete;

  ~TempDir() {
    std::error_code ec;
    fs::remove_all(path, ec);
    if (ec) {
      // Restore directory access for cleanup without following symlinks.
      writableDirectories(path);
      fs::remove_all(path, ec);
    }
  }

 private:
  static void writableDirectories(const fs::path& directory) {
    std::error_code ec;
    if (!fs::is_directory(fs::symlink_status(directory, ec))) {
      return;
    }
    fs::permissions(directory, fs::perms::owner_all,
                    fs::perm_options::add | fs::perm_options::nofollow, ec);
    if (ec) {
      return;
    }
    fs::directory_iterator end, it(directory, ec);
    while (!ec && it != end) {
      writableDirectories(it->path());
      it.increment(ec);
    }
  }
};
inline fs::path outputPath(const fs::path& p) {
  auto absolute = fs::absolute(p).lexically_normal();
  require(!absolute.filename().empty() && absolute != absolute.root_path(),
          "Output must have a file or directory name");
  require(fs::is_directory(absolute.parent_path()), "Output parent must exist");
  return fs::canonical(absolute.parent_path()) / absolute.filename();
}

inline bool beneath(const fs::path& child, const fs::path& parent) {
  auto c = child.begin();
  for (auto p = parent.begin(); p != parent.end(); ++p, ++c) {
    if (c == child.end() || *c != *p) {
      return false;
    }
  }
  return true;
}

inline bool existsNoFollow(const fs::path& p) {
  struct stat st {};
  if (::lstat(p.c_str(), &st) == 0) {
    return true;
  }
  syscheck(errno == ENOENT, "Cannot inspect output");
  return false;
}

inline void privateFile(const fs::path& p) {
  Fd fd(::open(p.c_str(), O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW, 0600));
  syscheck(fd.value >= 0, "Cannot create temporary file");
}

inline void syncFile(const fs::path& p) {
  Fd fd(::open(p.c_str(), O_RDONLY | O_NOFOLLOW));
  syscheck(fd.value >= 0 && ::fsync(fd.value) == 0, "Cannot flush file");
}
// Open each path component without following a changed parent symlink.
inline int openSource(const fs::path& root, const std::string& relative) {
  int current = ::open(root.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
  syscheck(current >= 0, "Cannot open source directory");
  fs::path path(relative);
  for (auto it = path.begin(); it != path.end(); ++it) {
    bool last = std::next(it) == path.end();
    int next = ::openat(current, it->c_str(),
                        O_RDONLY | O_NOFOLLOW | (last ? 0 : O_DIRECTORY) | O_NONBLOCK);
    int saved = errno;
    ::close(current);
    errno = saved;
    syscheck(next >= 0, "Cannot open source safely: " + relative);
    current = next;
  }
  return current;
}
}  // namespace squirrel
#endif  // SQUIRREL_INTERNAL_H_
