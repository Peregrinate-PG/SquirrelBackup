// Copyright 2026 Squirrel Backup course project.
#include <fnmatch.h>
#include <sys/xattr.h>

#include <algorithm>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "internal.h"

namespace squirrel {
bool Filter::excluded(const std::string& path) const {
  for (const auto& pattern : excludes) {
    if (::fnmatch(pattern.c_str(), path.c_str(), 0) == 0 ||
        ::fnmatch(pattern.c_str(), fs::path(path).filename().c_str(), 0) == 0) {
      return true;
    }
  }
  return false;
}

bool Filter::accepts(const std::string& path, const struct stat& st) const {
  if (S_ISDIR(st.st_mode)) {
    return true;
  }
  if (!path_pattern.empty() && ::fnmatch(path_pattern.c_str(), path.c_str(), 0)) {
    return false;
  }
  if (!name_pattern.empty() &&
      ::fnmatch(name_pattern.c_str(), fs::path(path).filename().c_str(), 0)) {
    return false;
  }
  char kind = S_ISREG(st.st_mode) ? 'f' : S_ISLNK(st.st_mode) ? 'l' : 'p';
  if (!types.empty() && types.find(kind) == std::string::npos) {
    return false;
  }
  if (owner >= 0 && st.st_uid != owner) {
    return false;
  }
  if (st.st_mtimespec.tv_sec < since || st.st_mtimespec.tv_sec > until) {
    return false;
  }
  return !S_ISREG(st.st_mode) || (static_cast<uint64_t>(st.st_size) >= min_size &&
                                  static_cast<uint64_t>(st.st_size) <= max_size);
}

std::string typeName(FileType type) {
  switch (type) {
    case FileType::Directory:
      return "directory";
    case FileType::Regular:
      return "file";
    case FileType::Symlink:
      return "symlink";
    case FileType::Hardlink:
      return "hardlink";
    case FileType::Fifo:
      return "fifo";
  }
  return "unknown";
}
namespace {
std::vector<std::pair<std::string, Bytes>> attributes(const fs::path& path,
                                                      const Operation& operation) {
  ssize_t n = ::listxattr(path.c_str(), nullptr, 0, XATTR_NOFOLLOW);
  if (n < 0 && (errno == ENOTSUP || errno == EPERM)) {
    return {};
  }
  syscheck(n >= 0, "Cannot list xattrs: " + path.string());
  require(n <= 1024 * 1024, "Extended attribute name list too large");
  std::vector<char> names(n);
  if (n) {
    syscheck(::listxattr(path.c_str(), names.data(), names.size(), XATTR_NOFOLLOW) == n,
             "Extended attributes changed during scan");
  }
  std::vector<std::pair<std::string, Bytes>> result;
  size_t offset = 0, total = 0;
  while (offset < names.size()) {
    operation.check();
    std::string name(names.data() + offset);
    offset += name.size() + 1;
    ssize_t len = ::getxattr(path.c_str(), name.c_str(), nullptr, 0, 0, XATTR_NOFOLLOW);
    syscheck(len >= 0, "Cannot read xattr: " + name);
    total += len;
    require(total <= kMaxAttributeBytes, "Extended attributes exceed 64 MiB per entry");
    Bytes value(len);
    syscheck(::getxattr(path.c_str(), name.c_str(), value.data(), value.size(), 0,
                        XATTR_NOFOLLOW) == len,
             "Extended attributes changed during scan");
    result.push_back({name, std::move(value)});
  }
  require(result.size() <= kMaxAttributeCount, "Too many extended attributes");
  return result;
}
}  // namespace
std::vector<Entry> FileScanner::scan(const fs::path& root, const Filter& filter, const Log& log,
                                     const Operation& operation) {
  operation.checkpoint(Phase::Scan);
  require(fs::is_directory(root), "Source must be a directory");
  require(filter.min_size <= filter.max_size && filter.since <= filter.until,
          "Invalid filter range");
  for (char c : filter.types) {
    require(c == 'f' || c == 'l' || c == 'p', "Types must contain only f, l, p");
  }
  std::vector<Entry> entries;
  std::map<std::pair<uint64_t, uint64_t>, std::string> hardlinks;
  std::function<void(const std::string&)> visit = [&](const std::string& relative) {
    operation.checkpoint(Phase::Scan, entries.size(), 0, relative);
    if (!relative.empty() && filter.excluded(relative)) {
      return;
    }
    fs::path path = root / relative;
    struct stat st {};
    syscheck(::lstat(path.c_str(), &st) == 0, "Cannot stat: " + relative);
    require(
        S_ISDIR(st.st_mode) || S_ISREG(st.st_mode) || S_ISLNK(st.st_mode) || S_ISFIFO(st.st_mode),
        "Unsupported special file (socket or device): " + relative);
    if (!filter.accepts(relative, st)) {
      return;
    }
    Entry entry;
    entry.path = relative;
    entry.mode = st.st_mode & 0777;
    entry.uid = st.st_uid;
    entry.gid = st.st_gid;
    entry.mtime = st.st_mtimespec.tv_sec;
    entry.mtime_ns = st.st_mtimespec.tv_nsec;
    entry.atime = st.st_atimespec.tv_sec;
    entry.atime_ns = st.st_atimespec.tv_nsec;
    entry.ctime = st.st_ctimespec.tv_sec;
    entry.ctime_ns = st.st_ctimespec.tv_nsec;
    entry.device = st.st_dev;
    entry.inode = st.st_ino;
    entry.type = S_ISDIR(st.st_mode)    ? FileType::Directory
                 : S_ISLNK(st.st_mode)  ? FileType::Symlink
                 : S_ISFIFO(st.st_mode) ? FileType::Fifo
                                        : FileType::Regular;
    if (entry.type == FileType::Symlink) {
      std::vector<char> buffer(65537);
      ssize_t len = ::readlink(path.c_str(), buffer.data(), buffer.size());
      syscheck(len >= 0, "Cannot read symlink: " + relative);
      require(size_t(len) < buffer.size(), "Symlink target too long");
      entry.link.assign(buffer.data(), len);
    }
    if (entry.type == FileType::Regular) {
      entry.size = st.st_size;
      require(entry.size <= kMaxFileSize,
              "Source file exceeds the 1 TiB format limit: " + relative);
      auto key = std::make_pair(entry.device, entry.inode);
      auto it = hardlinks.find(key);
      if (it != hardlinks.end()) {
        entry.type = FileType::Hardlink;
        entry.link = it->second;
      } else {
        hardlinks[key] = relative;
      }
    }
    entry.xattrs = attributes(path, operation);
    entries.push_back(std::move(entry));
    require(entries.size() <= kMaxEntries, "Entry limit exceeded (1 million)");
    if (S_ISDIR(st.st_mode)) {
      std::vector<std::string> children;
      for (const auto& child : fs::directory_iterator(path)) {
        operation.check();
        children.push_back(child.path().filename().string());
      }
      std::sort(children.begin(), children.end());
      for (const auto& child : children) {
        visit(relative.empty() ? child : relative + "/" + child);
      }
    }
  };
  visit("");
  emit(log, "Scanned " + std::to_string(entries.size()) + " entries");
  return entries;
}
}  // namespace squirrel
