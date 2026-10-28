// Copyright 2026 Squirrel Backup course project.
#include <chrono>
#include <deque>
#include <iomanip>
#include <sstream>
#include <string>
#include <thread>

#include "internal.h"
namespace squirrel {
namespace {
std::string fingerprint(const fs::path& source, const Filter& filter) {
  auto entries = FileScanner::scan(source, filter);
  // Metadata polling does not read file bodies and never changes their access time.
  std::ostringstream out;
  for (const auto& e : entries) {
    out << e.path.size() << ':' << e.path << ':' << int(e.type) << ':' << e.size << ':' << e.inode
        << ':' << e.mtime << ':' << e.mtime_ns << ':' << e.mode << ':' << e.uid << ':' << e.gid
        << ':' << e.link.size() << ':' << e.link << ':';
    for (const auto& a : e.xattrs) {
      out << a.first.size() << ':' << a.first << ':' << a.second.size() << ':';
      out.write(reinterpret_cast<const char*>(a.second.data()), a.second.size());
    }
  }
  return out.str();
}
}  // namespace
void Scheduler::run(const fs::path& source, const fs::path& repository,
                    const BackupOptions& options, const ScheduleOptions& schedule,
                    const std::atomic<bool>& stop, const Log& log) {
  require(schedule.interval_seconds >= 1 && schedule.poll_seconds >= 1 && schedule.keep >= 1,
          "Interval, poll seconds and retention must be positive");
  require(options.password.empty() || options.password.size() >= 8,
          "Use a password of at least 8 UTF-8 bytes");
  require(options.filter.min_size <= options.filter.max_size &&
              options.filter.since <= options.filter.until,
          "Invalid filter range");
  for (char c : options.filter.types) {
    require(c == 'f' || c == 'l' || c == 'p', "Types must contain only f, l, p");
  }
  auto root = fs::canonical(source), repo = fs::canonical(repository);
  require(fs::is_directory(repo) && !beneath(repo, root),
          "Repository must be an existing directory outside the source");
  // Each invocation owns a fresh isolated job folder. Retention never touches unrelated files.
  TempDir reservation(repo);
  auto job = repo / ("squirrel-job-" + reservation.path.filename().string().substr(10));
  syscheck(::renamex_np(reservation.path.c_str(), job.c_str(), RENAME_EXCL) == 0,
           "Cannot allocate job directory");
  emit(log, "Job repository: " + job.string());
  std::deque<fs::path> owned;
  std::string baseline, pending;
  uint32_t runs = 0;
  bool first = true;
  using Clock = std::chrono::steady_clock;
  auto last = Clock::now();
  while (!stop.load()) {
    try {
      bool due = first;
      std::string current;
      if (schedule.watch) {
        current = fingerprint(root, options.filter);
        due = first || (current != baseline && current == pending);
        pending = current;
      } else {
        due = first || Clock::now() - last >= std::chrono::seconds(schedule.interval_seconds);
      }
      if (due) {
        auto file = job / ("snapshot-" + std::to_string(runs + 1) + ".sqbk");
        BackupService{}.backup(root, file, options, log);
        owned.push_back(file);
        ++runs;
        // Commit snapshot state before best-effort retention. Cleanup failure must not
        // cause an extra backup, invalidate the watch baseline, or bypass max_runs.
        first = false;
        last = Clock::now();
        if (schedule.watch) {
          baseline = current;
        }
      }
      while (owned.size() > schedule.keep) {
        std::error_code error;
        fs::remove(owned.front(), error);
        if (error) {
          emit(log, "WARNING: retention cleanup failed; will retry without duplicating backup: " +
                        owned.front().filename().string() + ": " + error.message());
          break;
        }
        emit(log, "Retention removed: " + owned.front().filename().string());
        owned.pop_front();
      }
      if (schedule.max_runs && runs >= schedule.max_runs) {
        break;
      }
    } catch (const std::exception& error) {
      emit(log, "WARNING: scheduled backup failed; will retry: " + std::string(error.what()));
    }
    uint32_t delay = schedule.watch ? schedule.poll_seconds * 10 : 10;
    for (uint32_t i = 0; i < delay && !stop.load(); ++i) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
  }
  emit(log, "Job stopped; completed snapshots: " + std::to_string(runs));
}
}  // namespace squirrel
