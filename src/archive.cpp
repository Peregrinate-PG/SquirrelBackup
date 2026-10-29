// Copyright 2026 Squirrel Backup course project.
#include <sys/xattr.h>

#include <algorithm>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "internal.h"
namespace squirrel {
namespace {
class Writer {
 public:
  std::ofstream stream;
  explicit Writer(const fs::path& path) {
    privateFile(path);
    stream.open(path, std::ios::binary);
  }
  void bytes(const void* p, size_t n) {
    stream.write(static_cast<const char*>(p), n);
    require(static_cast<bool>(stream), "Cannot write archive (disk full?)");
  }
  void number(uint64_t n, int width) {
    for (int i = 0; i < width; ++i) {
      uint8_t b = n >> (8 * i);
      bytes(&b, 1);
    }
  }
  void text(const std::string& s) {
    require(s.size() <= 65536, "Archive text too long");
    number(s.size(), 4);
    bytes(s.data(), s.size());
  }
};
class Reader {
 public:
  std::ifstream stream;
  explicit Reader(const fs::path& path) : stream(path, std::ios::binary) {
    require(static_cast<bool>(stream), "Cannot open tree archive");
  }
  void bytes(void* p, size_t n) {
    stream.read(static_cast<char*>(p), n);
    require(static_cast<bool>(stream), "Truncated tree archive");
  }
  uint64_t number(int width) {
    uint64_t n = 0;
    for (int i = 0; i < width; ++i) {
      uint8_t b;
      bytes(&b, 1);
      n |= static_cast<uint64_t>(b) << (8 * i);
    }
    return n;
  }
  std::string text() {
    size_t n = number(4);
    require(n <= 65536, "Archive text limit exceeded");
    std::string s(n, '\0');
    bytes(s.data(), n);
    require(s.find('\0') == std::string::npos, "NUL in archive text");
    return s;
  }
};
void writeEntry(Writer& w, const Entry& e) {
  w.number(static_cast<uint8_t>(e.type), 1);
  w.text(e.path);
  w.number(e.mode, 4);
  w.number(e.uid, 4);
  w.number(e.gid, 4);
  w.number(static_cast<uint64_t>(e.mtime), 8);
  w.number(e.mtime_ns, 4);
  w.number(static_cast<uint64_t>(e.atime), 8);
  w.number(e.atime_ns, 4);
  w.number(e.size, 8);
  w.text(e.link);
  w.number(e.xattrs.size(), 4);
  for (const auto& pair : e.xattrs) {
    w.text(pair.first);
    w.number(pair.second.size(), 4);
    w.bytes(pair.second.data(), pair.second.size());
  }
}
Entry readEntry(Reader& r) {
  Entry e;
  e.type = static_cast<FileType>(r.number(1));
  e.path = r.text();
  e.mode = r.number(4);
  e.uid = r.number(4);
  e.gid = r.number(4);
  e.mtime = static_cast<int64_t>(r.number(8));
  e.mtime_ns = r.number(4);
  e.atime = static_cast<int64_t>(r.number(8));
  e.atime_ns = r.number(4);
  e.size = r.number(8);
  e.link = r.text();
  require(e.mode <= 0777 && e.mtime_ns < 1000000000 && e.atime_ns < 1000000000,
          "Invalid metadata fields");
  require(e.size <= (static_cast<uint64_t>(1) << 40), "Entry exceeds 1 TiB size limit");
  uint64_t count = r.number(4), total = 0;
  require(count <= 4096, "Too many attributes");
  std::set<std::string> names;
  for (uint64_t i = 0; i < count; ++i) {
    auto name = r.text();
    require(!name.empty() && names.insert(name).second, "Invalid xattr name");
    uint64_t n = r.number(4);
    total += n;
    require(total <= 64 * 1024 * 1024, "Attribute memory limit exceeded");
    Bytes value(n);
    r.bytes(value.data(), n);
    e.xattrs.push_back({name, std::move(value)});
  }
  return e;
}
void validatePath(const std::string& s) {
  require(!s.empty() && s.front() != '/' && s.back() != '/', "Invalid relative path");
  require(s.find("//") == std::string::npos, "Empty path component");
  for (const auto& part : fs::path(s)) {
    require(part != "." && part != "..", "Unsafe archive path");
  }
}
void metadata(const fs::path& path, const Entry& e, const Log& log) {
  // Owner IDs are recorded; restoring different owners requires privileges and is best effort.
  struct stat st{};
  syscheck(::lstat(path.c_str(), &st) == 0, "Cannot stat restored entry");
  if (st.st_uid != e.uid || st.st_gid != e.gid) {
    if (::lchown(path.c_str(), e.uid, e.gid) != 0) {
      emit(log, "WARNING: owner/group not restored: " + e.path);
    }
  }
  for (const auto& pair : e.xattrs) {
    if (::setxattr(path.c_str(), pair.first.c_str(), pair.second.data(), pair.second.size(), 0,
                   XATTR_NOFOLLOW) != 0) {
      emit(log, "WARNING: xattr not restored: " + e.path + " / " + pair.first);
    }
  }
  if (e.type != FileType::Symlink) {
    syscheck(::chmod(path.c_str(), e.mode) == 0, "Cannot restore permissions: " + e.path);
  }
  struct timespec times[2] = {{e.atime, e.atime_ns}, {e.mtime, e.mtime_ns}};
  syscheck(::utimensat(AT_FDCWD, path.c_str(), times, AT_SYMLINK_NOFOLLOW) == 0,
           "Cannot restore timestamps: " + e.path);
}
}  // namespace
void ArchiveWriter::write(const fs::path& source, const std::vector<Entry>& entries,
                          const fs::path& output, bool compress, const Log& log) {
  Writer w(output);
  w.bytes("SQTREE01", 8);
  w.number(entries.size(), 8);
  for (const auto& e : entries) {
    writeEntry(w, e);
    if (e.type != FileType::Regular) {
      continue;
    }
    Fd fd(openSource(source, e.path));
    struct stat st{};
    syscheck(::fstat(fd.value, &st) == 0, "Cannot stat opened source");
    auto unchanged = [&]() {
      return S_ISREG(st.st_mode) && static_cast<uint64_t>(st.st_dev) == e.device &&
             static_cast<uint64_t>(st.st_ino) == e.inode &&
             static_cast<uint64_t>(st.st_size) == e.size && st.st_mtimespec.tv_sec == e.mtime &&
             st.st_mtimespec.tv_nsec == e.mtime_ns && st.st_ctimespec.tv_sec == e.ctime &&
             st.st_ctimespec.tv_nsec == e.ctime_ns;
    };
    require(unchanged(), "Source changed before backup: " + e.path);
    uint64_t remaining = e.size;
    while (remaining) {
      size_t n = std::min<uint64_t>(remaining, kBlockSize);
      Bytes data(n);
      size_t offset = 0;
      while (offset < n) {
        ssize_t got = ::read(fd.value, data.data() + offset, n - offset);
        if (got < 0 && errno == EINTR) {
          continue;
        }
        require(got > 0, "Source changed or cannot be read: " + e.path);
        offset += got;
      }
      Bytes packed = compress ? HuffmanCodec::encode(data) : Bytes{};
      bool use = compress && packed.size() < data.size();
      const Bytes& payload = use ? packed : data;
      w.number(use ? 1 : 0, 1);
      w.number(n, 4);
      w.number(payload.size(), 4);
      w.bytes(payload.data(), payload.size());
      remaining -= n;
    }
    syscheck(::fstat(fd.value, &st) == 0, "Cannot recheck source");
    require(unchanged(), "Source changed while backing up: " + e.path);
    emit(log, "Packed: " + e.path);
  }
  w.bytes("SQEND001", 8);
  w.stream.close();
  require(static_cast<bool>(w.stream), "Cannot finish archive");
}
Summary ArchiveReader::read(const fs::path& plain, const fs::path* destination, const Log& log,
                            bool collect) {
  Reader r(plain);
  char magic[8];
  r.bytes(magic, 8);
  require(std::string(magic, 8) == "SQTREE01", "Unknown tree format");
  uint64_t count = r.number(8);
  require(count > 0 && count <= 1000000, "Invalid entry count");
  Summary result;
  std::map<std::string, std::pair<FileType, uint64_t>> seen;
  std::vector<Entry> directories;
  for (uint64_t i = 0; i < count; ++i) {
    Entry e = readEntry(r);
    if (i == 0) {
      require(e.path.empty() && e.type == FileType::Directory, "Missing root directory");
    } else {
      validatePath(e.path);
      auto parent = fs::path(e.path).parent_path().generic_string();
      auto it = seen.find(parent);
      require(it != seen.end() && it->second.first == FileType::Directory,
              "Parent is missing or is not a directory");
    }
    require(seen.emplace(e.path, std::make_pair(e.type, e.size)).second, "Duplicate archive path");
    fs::path path = destination ? *destination / e.path : fs::path{};
    switch (e.type) {
      case FileType::Directory:
        require(e.size == 0 && e.link.empty(), "Invalid directory record");
        if (destination) {
          if (i) {
            syscheck(::mkdir(path.c_str(), 0700) == 0, "Cannot create directory: " + e.path);
          }
          directories.push_back(e);
        }
        break;
      case FileType::Regular: {
        require(e.link.empty(), "Invalid regular file record");
        int raw = -1;
        if (destination) {
          raw = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
          syscheck(raw >= 0, "Cannot create file: " + e.path);
        }
        Fd out(raw);
        uint64_t remaining = e.size;
        while (remaining) {
          uint64_t coding = r.number(1), n = r.number(4), packed = r.number(4);
          require(coding <= 1 && n > 0 && n <= kBlockSize && n <= remaining &&
                      packed <= kBlockSize && (coding == 1 || packed == n),
                  "Invalid archive data block");
          Bytes data(packed);
          r.bytes(data.data(), packed);
          if (coding) {
            data = HuffmanCodec::decode(data, n);
          }
          if (destination) {
            size_t offset = 0;
            while (offset < data.size()) {
              ssize_t wrote = ::write(out.value, data.data() + offset, data.size() - offset);
              if (wrote < 0 && errno == EINTR) {
                continue;
              }
              syscheck(wrote > 0, "Cannot write restored file (disk full?)");
              offset += wrote;
            }
          }
          remaining -= n;
        }
        ++result.files;
        result.bytes += e.size;
        break;
      }
      case FileType::Hardlink: {
        validatePath(e.link);
        auto it = seen.find(e.link);
        require(it != seen.end() && it->second.first == FileType::Regular &&
                    it->second.second == e.size,
                "Invalid hardlink target");
        if (destination) {
          syscheck(::link((*destination / e.link).c_str(), path.c_str()) == 0,
                   "Cannot restore hardlink");
        }
        ++result.files;
        result.bytes += e.size;
        break;
      }
      case FileType::Symlink:
        require(e.size == 0 && !e.link.empty(), "Invalid symlink record");
        if (destination) {
          syscheck(::symlink(e.link.c_str(), path.c_str()) == 0, "Cannot restore symlink");
        }
        break;
      case FileType::Fifo:
        require(e.size == 0 && e.link.empty(), "Invalid FIFO record");
        if (destination) {
          syscheck(::mkfifo(path.c_str(), 0600) == 0, "Cannot restore FIFO");
        }
        break;
      default:
        throw Error("Unsupported archive entry type");
    }
    if (destination && e.type != FileType::Directory) {
      metadata(path, e, log);
    }
    ++result.entries;
    if (collect) {
      result.items.push_back(std::move(e));
    }
  }
  r.bytes(magic, 8);
  require(std::string(magic, 8) == "SQEND001" && r.stream.peek() == EOF,
          "Invalid archive footer or trailing data");
  if (destination) {
    for (auto it = directories.rbegin(); it != directories.rend(); ++it) {
      metadata(*destination / it->path, *it, log);
    }
  }
  return result;
}
}  // namespace squirrel
