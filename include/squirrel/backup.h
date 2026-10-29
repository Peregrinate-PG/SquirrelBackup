// Copyright 2026 Squirrel Backup course project.
#ifndef SQUIRREL_BACKUP_H_
#define SQUIRREL_BACKUP_H_
#include <sys/stat.h>

#include <atomic>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace squirrel {
namespace fs = std::filesystem;
using Bytes = std::vector<uint8_t>;
using Log = std::function<void(const std::string&)>;
constexpr uint32_t kBlockSize = 1024 * 1024;
struct Error : std::runtime_error {
  using std::runtime_error::runtime_error;
};
enum class FileType : uint8_t { Directory = 1, Regular = 2, Symlink = 3, Hardlink = 4, Fifo = 5 };
struct Filter {
  std::vector<std::string> excludes;
  std::string path_pattern;
  std::string name_pattern;
  std::string types;  // f = regular (including hardlinks), l = symlink, p = FIFO.
  uint64_t min_size = 0, max_size = std::numeric_limits<uint64_t>::max();
  int64_t since = std::numeric_limits<int64_t>::min();
  int64_t until = std::numeric_limits<int64_t>::max();
  int64_t owner = -1;
  bool excluded(const std::string& path) const;
  bool accepts(const std::string& path, const struct stat& st) const;
};
struct Entry {
  std::string path, link;
  FileType type = FileType::Regular;
  uint32_t mode = 0, uid = 0, gid = 0;
  int64_t mtime = 0, atime = 0;
  uint32_t mtime_ns = 0, atime_ns = 0;
  // Scan-only change detection. These fields are not serialized in SQTREE01.
  int64_t ctime = 0;
  uint32_t ctime_ns = 0;
  uint64_t size = 0, device = 0, inode = 0;
  std::vector<std::pair<std::string, Bytes>> xattrs;
};
struct BackupOptions {
  Filter filter;
  bool compress = true;
  std::string password;
};
struct Summary {
  uint64_t entries = 0, files = 0, bytes = 0, archive_bytes = 0;
  std::vector<Entry> items;
};
class HuffmanCodec {
 public:
  static Bytes encode(const Bytes& input);
  static Bytes decode(const Bytes& input, uint32_t expected);
};
class FileScanner {
 public:
  static std::vector<Entry> scan(const fs::path& root, const Filter& filter, const Log& log = {});
};
class CryptoEnvelope {
 public:
  static void seal(const fs::path& plain, const fs::path& output, const std::string& password);
  static void open(const fs::path& archive, const fs::path& plain, const std::string& password);
};
class ArchiveWriter {
 public:
  static void write(const fs::path& source, const std::vector<Entry>& entries,
                    const fs::path& output, bool compress, const Log& log);
};
class ArchiveReader {
 public:
  static Summary read(const fs::path& plain, const fs::path* destination, const Log& log,
                      bool collect = true);
};
class BackupService {
 public:
  Summary backup(const fs::path& source, const fs::path& archive, const BackupOptions& options = {},
                 const Log& log = {}) const;
  Summary inspect(const fs::path& archive, const std::string& password = "", const Log& log = {},
                  bool collect = true) const;
  Summary restore(const fs::path& archive, const fs::path& destination,
                  const std::string& password = "", const Log& log = {}) const;
};
struct ScheduleOptions {
  uint32_t interval_seconds = 300, keep = 5, poll_seconds = 2;
  bool watch = false;
  uint32_t max_runs = 0;  // 0 = unlimited; useful for unattended demonstrations.
};
class Scheduler {
 public:
  static void run(const fs::path& source, const fs::path& repository, const BackupOptions& backup,
                  const ScheduleOptions& options, const std::atomic<bool>& stop, const Log& log);
};
std::string typeName(FileType type);
}  // namespace squirrel
#endif  // SQUIRREL_BACKUP_H_
