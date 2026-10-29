// Copyright 2026 Squirrel Backup course project.
#include <cstdio>
#include <string>
#include <vector>

#include "internal.h"
namespace squirrel {
namespace {
bool sameSource(const std::vector<Entry>& a, const std::vector<Entry>& b) {
  if (a.size() != b.size()) {
    return false;
  }
  for (size_t i = 0; i < a.size(); ++i) {
    const auto& x = a[i];
    const auto& y = b[i];
    // Access times may legitimately change when files are read. Everything else
    // which identifies an entry or supplies restored metadata must remain stable.
    if (x.path != y.path || x.type != y.type || x.device != y.device || x.inode != y.inode ||
        x.size != y.size || x.mode != y.mode || x.uid != y.uid || x.gid != y.gid ||
        x.mtime != y.mtime || x.mtime_ns != y.mtime_ns || x.ctime != y.ctime ||
        x.ctime_ns != y.ctime_ns || x.link != y.link || x.xattrs != y.xattrs) {
      return false;
    }
  }
  return true;
}
}  // namespace
Summary BackupService::backup(const fs::path& source, const fs::path& archive,
                              const BackupOptions& options, const Log& log,
                              const Operation& operation) const {
  operation.check();
  fs::path root = fs::canonical(source), output = outputPath(archive);
  require(fs::is_directory(root), "Source must be a directory");
  require(!beneath(output, root), "Backup output must be outside the source tree");
  require(!existsNoFollow(output), "Backup output already exists; choose a new filename");
  require(options.password.empty() || options.password.size() >= 8,
          "Use a password of at least 8 UTF-8 bytes");
  auto entries = FileScanner::scan(root, options.filter, log, operation);
  TempDir temp(output.parent_path());
  auto packed = temp.path / "tree", sealed = temp.path / "sealed";
  ArchiveWriter::write(root, entries, packed, options.compress, log, operation);
  CryptoEnvelope::seal(packed, sealed, options.password, operation);
  operation.checkpoint(Phase::CheckSource);
  Operation recheck{operation.stop, {}};
  require(sameSource(entries, FileScanner::scan(root, options.filter, {}, recheck)),
          "Source changed during backup; no archive was published. "
          "Try again when files are stable");
  syncFile(sealed);
  Summary summary;
  for (const auto& e : entries) {
    ++summary.entries;
    if (e.type == FileType::Regular || e.type == FileType::Hardlink) {
      ++summary.files;
      summary.bytes += e.size;
    }
  }
  summary.archive_bytes = fs::file_size(sealed);
  operation.checkpoint(Phase::Publish);
  // link(2) publishes a fully written file without overwriting any concurrent target.
  syscheck(::link(sealed.c_str(), output.c_str()) == 0,
           "Cannot publish backup without overwriting");
  emit(log, "Backup complete: " + output.string());
  return summary;
}
Summary BackupService::inspect(const fs::path& archive, const std::string& password, const Log& log,
                               bool collect, const Operation& operation) const {
  operation.check();
  TempDir temp;
  auto plain = temp.path / "tree";
  CryptoEnvelope::open(archive, plain, password, operation);
  auto result = ArchiveReader::read(plain, nullptr, log, collect, operation);
  result.archive_bytes = fs::file_size(archive);
  emit(log, "Verification passed: " + std::to_string(result.entries) + " entries");
  return result;
}
Summary BackupService::restore(const fs::path& archive, const fs::path& destination,
                               const std::string& password, const Log& log,
                               const Operation& operation) const {
  operation.check();
  auto output = outputPath(destination);
  require(!existsNoFollow(output),
          "Restore destination must not already exist; choose a new folder name");
  TempDir temp(output.parent_path());
  auto plain = temp.path / "tree", stage = temp.path / "restored";
  CryptoEnvelope::open(archive, plain, password, operation);
  syscheck(::mkdir(stage.c_str(), 0700) == 0, "Cannot create staging directory");
  Fd stage_fd(::open(stage.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW));
  syscheck(stage_fd.value >= 0, "Cannot open staging directory");
  auto summary = ArchiveReader::read(plain, &stage, log, false, operation);
  struct stat restored_root{};
  syscheck(::fstat(stage_fd.value, &restored_root) == 0, "Cannot inspect restored root");
  // macOS needs owner write/search permission to move a directory to a new parent.
  // Keep its descriptor open so final permissions can be set even for mode 000.
  const mode_t final_mode = restored_root.st_mode & 0777;
  syscheck(::fchmod(stage_fd.value, final_mode | 0700) == 0,
           "Cannot prepare restored directory for publication");
  summary.archive_bytes = fs::file_size(archive);
  // macOS exclusive directory rename prevents clobbering a concurrently created destination.
  operation.checkpoint(Phase::Publish);
  syscheck(::renamex_np(stage.c_str(), output.c_str(), RENAME_EXCL) == 0,
           "Cannot publish restored directory without overwriting");
  syscheck(::fchmod(stage_fd.value, final_mode) == 0, "Cannot finalize restored root permissions");
  emit(log, "Restore complete: " + output.string());
  return summary;
}
}  // namespace squirrel
