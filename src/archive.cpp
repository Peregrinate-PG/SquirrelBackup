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
    require(s.size() <= kMaxTextSize, "Archive text too long");
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
    require(n <= kMaxTextSize, "Archive text limit exceeded");
    std::string s(n, '\0');
    bytes(s.data(), n);
    require(s.find('\0') == std::string::npos, "NUL in archive text");
    return s;
  }
};
void writeEntry(Writer& writer, const Entry& entry) {
  writer.number(static_cast<uint8_t>(entry.type), 1);
  writer.text(entry.path);
  writer.number(entry.mode, 4);
  writer.number(entry.uid, 4);
  writer.number(entry.gid, 4);
  writer.number(static_cast<uint64_t>(entry.mtime), 8);
  writer.number(entry.mtime_ns, 4);
  writer.number(static_cast<uint64_t>(entry.atime), 8);
  writer.number(entry.atime_ns, 4);
  writer.number(entry.size, 8);
  writer.text(entry.link);
  writer.number(entry.xattrs.size(), 4);
  for (const auto& pair : entry.xattrs) {
    writer.text(pair.first);
    writer.number(pair.second.size(), 4);
    writer.bytes(pair.second.data(), pair.second.size());
  }
}

Entry readEntry(Reader& reader) {
  Entry entry;
  entry.type = static_cast<FileType>(reader.number(1));
  entry.path = reader.text();
  entry.mode = reader.number(4);
  entry.uid = reader.number(4);
  entry.gid = reader.number(4);
  entry.mtime = static_cast<int64_t>(reader.number(8));
  entry.mtime_ns = reader.number(4);
  entry.atime = static_cast<int64_t>(reader.number(8));
  entry.atime_ns = reader.number(4);
  entry.size = reader.number(8);
  entry.link = reader.text();
  require(entry.mode <= 0777 && entry.mtime_ns < 1000000000 && entry.atime_ns < 1000000000,
          "Invalid metadata fields");
  require(entry.size <= kMaxFileSize, "Entry exceeds 1 TiB size limit");
  uint64_t count = reader.number(4), total = 0;
  require(count <= kMaxAttributeCount, "Too many attributes");
  std::set<std::string> names;
  for (uint64_t i = 0; i < count; ++i) {
    auto name = reader.text();
    require(!name.empty() && names.insert(name).second, "Invalid xattr name");
    uint64_t n = reader.number(4);
    total += n;
    require(total <= kMaxAttributeBytes, "Attribute memory limit exceeded");
    Bytes value(n);
    reader.bytes(value.data(), n);
    entry.xattrs.push_back({name, std::move(value)});
  }
  return entry;
}

void validatePath(const std::string& s) {
  require(!s.empty() && s.front() != '/' && s.back() != '/', "Invalid relative path");
  require(s.find("//") == std::string::npos, "Empty path component");
  for (const auto& part : fs::path(s)) {
    require(part != "." && part != "..", "Unsafe archive path");
  }
}

void metadata(const fs::path& path, const Entry& entry, const Log& log) {
  // Owner IDs are recorded; restoring different owners requires privileges and is best effort.
  struct stat st {};
  syscheck(::lstat(path.c_str(), &st) == 0, "Cannot stat restored entry");
  if (st.st_uid != entry.uid || st.st_gid != entry.gid) {
    if (::lchown(path.c_str(), entry.uid, entry.gid) != 0) {
      emit(log, "WARNING: owner/group not restored: " + entry.path);
    }
  }
  for (const auto& pair : entry.xattrs) {
    if (::setxattr(path.c_str(), pair.first.c_str(), pair.second.data(), pair.second.size(), 0,
                   XATTR_NOFOLLOW) != 0) {
      emit(log, "WARNING: xattr not restored: " + entry.path + " / " + pair.first);
    }
  }
  if (entry.type != FileType::Symlink) {
    syscheck(::chmod(path.c_str(), entry.mode) == 0, "Cannot restore permissions: " + entry.path);
  }
  struct timespec times[2] = {{entry.atime, entry.atime_ns}, {entry.mtime, entry.mtime_ns}};
  syscheck(::utimensat(AT_FDCWD, path.c_str(), times, AT_SYMLINK_NOFOLLOW) == 0,
           "Cannot restore timestamps: " + entry.path);
}
}  // namespace
void ArchiveWriter::write(const fs::path& source, const std::vector<Entry>& entries,
                          const fs::path& output, bool compress, const Log& log,
                          const Operation& operation) {
  uint64_t total = 0, completed = 0;
  for (const auto& entry : entries) {
    if (entry.type == FileType::Regular) {
      total += entry.size;
    }
  }
  operation.checkpoint(Phase::Pack, 0, total);
  Writer writer(output);
  writer.bytes("SQTREE01", 8);
  writer.number(entries.size(), 8);
  for (const auto& entry : entries) {
    operation.checkpoint(Phase::Pack, completed, total, entry.path);
    writeEntry(writer, entry);
    if (entry.type != FileType::Regular) {
      continue;
    }
    Fd fd(openSource(source, entry.path));
    struct stat st {};
    syscheck(::fstat(fd.value, &st) == 0, "Cannot stat opened source");
    auto unchanged = [&]() {
      return S_ISREG(st.st_mode) && static_cast<uint64_t>(st.st_dev) == entry.device &&
             static_cast<uint64_t>(st.st_ino) == entry.inode &&
             static_cast<uint64_t>(st.st_size) == entry.size &&
             st.st_mtimespec.tv_sec == entry.mtime && st.st_mtimespec.tv_nsec == entry.mtime_ns &&
             st.st_ctimespec.tv_sec == entry.ctime && st.st_ctimespec.tv_nsec == entry.ctime_ns;
    };
    require(unchanged(), "Source changed before backup: " + entry.path);
    uint64_t remaining = entry.size;
    while (remaining) {
      operation.checkpoint(Phase::Pack, completed, total, entry.path);
      size_t n = std::min<uint64_t>(remaining, kBlockSize);
      Bytes data(n);
      size_t offset = 0;
      while (offset < n) {
        ssize_t got = ::read(fd.value, data.data() + offset, n - offset);
        if (got < 0 && errno == EINTR) {
          continue;
        }
        require(got > 0, "Source changed or cannot be read: " + entry.path);
        offset += got;
      }
      Bytes packed = compress ? HuffmanCodec::encode(data) : Bytes{};
      const bool useCompressed = compress && packed.size() < data.size();
      const Bytes& payload = useCompressed ? packed : data;
      writer.number(useCompressed ? 1 : 0, 1);
      writer.number(n, 4);
      writer.number(payload.size(), 4);
      writer.bytes(payload.data(), payload.size());
      remaining -= n;
      completed += n;
    }
    syscheck(::fstat(fd.value, &st) == 0, "Cannot recheck source");
    require(unchanged(), "Source changed while backing up: " + entry.path);
    emit(log, "Packed: " + entry.path);
  }
  operation.checkpoint(Phase::Pack, completed, total);
  writer.bytes("SQEND001", 8);
  writer.stream.close();
  require(static_cast<bool>(writer.stream), "Cannot finish archive");
}

Summary ArchiveReader::read(const fs::path& plain, const fs::path* destination, const Log& log,
                            bool collect, const Operation& operation) {
  const auto total = fs::file_size(plain);
  operation.checkpoint(Phase::Read, 0, total);
  Reader reader(plain);
  char magic[8];
  reader.bytes(magic, 8);
  require(std::string(magic, 8) == "SQTREE01", "Unknown tree format");
  uint64_t count = reader.number(8);
  require(count > 0 && count <= kMaxEntries, "Invalid entry count");
  Summary result;
  std::map<std::string, std::pair<FileType, uint64_t>> seen;
  std::vector<Entry> directories;
  for (uint64_t i = 0; i < count; ++i) {
    operation.checkpoint(Phase::Read, static_cast<uint64_t>(reader.stream.tellg()), total);
    Entry entry = readEntry(reader);
    if (i == 0) {
      require(entry.path.empty() && entry.type == FileType::Directory, "Missing root directory");
    } else {
      validatePath(entry.path);
      auto parent = fs::path(entry.path).parent_path().generic_string();
      auto it = seen.find(parent);
      require(it != seen.end() && it->second.first == FileType::Directory,
              "Parent is missing or is not a directory");
    }
    require(seen.emplace(entry.path, std::make_pair(entry.type, entry.size)).second,
            "Duplicate archive path");
    fs::path path = destination ? *destination / entry.path : fs::path{};
    switch (entry.type) {
      case FileType::Directory:
        require(entry.size == 0 && entry.link.empty(), "Invalid directory record");
        if (destination) {
          if (i) {
            syscheck(::mkdir(path.c_str(), 0700) == 0, "Cannot create directory: " + entry.path);
          }
          directories.push_back(entry);
        }
        break;
      case FileType::Regular: {
        require(entry.link.empty(), "Invalid regular file record");
        int raw = -1;
        if (destination) {
          raw = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
          syscheck(raw >= 0, "Cannot create file: " + entry.path);
        }
        Fd out(raw);
        uint64_t remaining = entry.size;
        while (remaining) {
          operation.checkpoint(Phase::Read, static_cast<uint64_t>(reader.stream.tellg()), total,
                               entry.path);
          uint64_t coding = reader.number(1), n = reader.number(4), packed = reader.number(4);
          require(coding <= 1 && n > 0 && n <= kBlockSize && n <= remaining &&
                      packed <= kBlockSize && (coding == 1 || packed == n),
                  "Invalid archive data block");
          Bytes data(packed);
          reader.bytes(data.data(), packed);
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
        result.bytes += entry.size;
        break;
      }
      case FileType::Hardlink: {
        validatePath(entry.link);
        auto it = seen.find(entry.link);
        require(it != seen.end() && it->second.first == FileType::Regular &&
                    it->second.second == entry.size,
                "Invalid hardlink target");
        if (destination) {
          syscheck(::link((*destination / entry.link).c_str(), path.c_str()) == 0,
                   "Cannot restore hardlink");
        }
        ++result.files;
        result.bytes += entry.size;
        break;
      }
      case FileType::Symlink:
        require(entry.size == 0 && !entry.link.empty(), "Invalid symlink record");
        if (destination) {
          syscheck(::symlink(entry.link.c_str(), path.c_str()) == 0, "Cannot restore symlink");
        }
        break;
      case FileType::Fifo:
        require(entry.size == 0 && entry.link.empty(), "Invalid FIFO record");
        if (destination) {
          syscheck(::mkfifo(path.c_str(), 0600) == 0, "Cannot restore FIFO");
        }
        break;
      default:
        throw Error("Unsupported archive entry type");
    }
    if (destination && entry.type != FileType::Directory) {
      metadata(path, entry, log);
    }
    ++result.entries;
    if (collect) {
      result.items.push_back(std::move(entry));
    }
  }
  reader.bytes(magic, 8);
  require(std::string(magic, 8) == "SQEND001" && reader.stream.peek() == EOF,
          "Invalid archive footer or trailing data");
  if (destination) {
    uint64_t applied = 0;
    for (auto it = directories.rbegin(); it != directories.rend(); ++it) {
      operation.checkpoint(Phase::Metadata, applied++, directories.size(), it->path);
      metadata(*destination / it->path, *it, log);
    }
  }
  operation.check();
  return result;
}
}  // namespace squirrel
