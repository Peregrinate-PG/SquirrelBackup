// Copyright 2026 Squirrel Backup course project.
#include <csignal>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <set>
#include <string>

#include "squirrel/backup.h"

namespace {
std::atomic<bool> stopped{false};
static_assert(std::atomic<bool>::is_always_lock_free, "Signal stop flag must be lock-free");
void onSignal(int) { stopped.store(true); }
void help() {
  std::cout << R"(Squirrel Backup 0.2.0 - macOS C++ backup software
Usage:
  squirrel backup SOURCE ARCHIVE [options]
  squirrel restore ARCHIVE NEW_FOLDER [--password-env ENV_NAME]
  squirrel list ARCHIVE [--password-env ENV_NAME]
  squirrel verify ARCHIVE [--password-env ENV_NAME]
  squirrel schedule SOURCE REPOSITORY [options] [--every SECONDS] [--keep N]
  squirrel watch SOURCE REPOSITORY [options] [--poll SECONDS] [--keep N]
Options:
  --no-compress          Store raw blocks instead of automatic Huffman
  --password-env NAME    Read password from an environment variable (not argv)
  --exclude GLOB         Exclude paths or basenames; repeatable; prunes directories
  --path GLOB            Include matching relative paths (directories retained)
  --name GLOB            Include matching basenames
  --type flp            Include regular files / symlinks / FIFOs
  --min-size BYTES       Minimum regular file size
  --max-size BYTES       Maximum regular file size
  --since EPOCH          Minimum modification time (Unix seconds)
  --until EPOCH          Maximum modification time (Unix seconds)
  --owner UID            Only entries belonging to this numeric user ID
  --every SECONDS        Schedule interval (schedule only), default 300
  --poll SECONDS         Watch polling interval (watch only), default 2 (debounced)
  --keep N               Retain latest N snapshots in this job, default 5
  --runs N               Stop after N successful snapshots; default unlimited
  --quiet               Suppress progress messages
Restore never overwrites an existing path. Outputs must be outside source.
Jobs run while this process is alive. Ctrl+C cancels the current operation safely.
)";
}
uint64_t number(const std::string& value) {
  if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos) {
    throw squirrel::Error("Expected a non-negative integer: " + value);
  }
  size_t used = 0;
  auto n = std::stoull(value, &used);
  if (used != value.size()) {
    throw squirrel::Error("Invalid integer");
  }
  return n;
}

struct Arguments {
  squirrel::BackupOptions backup;
  squirrel::ScheduleOptions schedule;
  bool quiet = false;
};

Arguments parseOptions(int argc, char** argv, int begin, const std::string& command) {
  using squirrel::Error;
  Arguments parsed;
  auto& options = parsed.backup;
  auto& schedule = parsed.schedule;
  schedule.watch = command == "watch";
  auto& quiet = parsed.quiet;
  std::set<std::string> used;
  for (int i = begin; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg != "--exclude" && !used.insert(arg).second) {
      throw Error("Duplicate option: " + arg);
    }
    if (arg == "--quiet") {
      quiet = true;
      continue;
    }
    if (arg == "--no-compress") {
      if (command == "restore" || command == "list" || command == "verify") {
        throw Error("Option not valid for this command");
      }
      options.compress = false;
      continue;
    }
    if (++i >= argc) {
      throw Error("Missing value for " + arg);
    }
    std::string value = argv[i];
    if (arg == "--password-env") {
      const char* password = std::getenv(value.c_str());
      if (!password || !*password) {
        throw Error("Password environment variable is missing or empty");
      }
      options.password = password;
    } else {
      if (command == "restore" || command == "list" || command == "verify") {
        throw Error("Option not valid for this command: " + arg);
      }
      if (arg == "--exclude") {
        options.filter.excludes.push_back(value);
      } else if (arg == "--path") {
        options.filter.path_pattern = value;
      } else if (arg == "--name") {
        options.filter.name_pattern = value;
      } else if (arg == "--type") {
        options.filter.types = value;
      } else if (arg == "--min-size") {
        options.filter.min_size = number(value);
      } else if (arg == "--max-size") {
        options.filter.max_size = number(value);
      } else if (arg == "--since") {
        auto n = number(value);
        if (n > INT64_MAX) {
          throw Error("Time out of range");
        }
        options.filter.since = n;
      } else if (arg == "--until") {
        auto n = number(value);
        if (n > INT64_MAX) {
          throw Error("Time out of range");
        }
        options.filter.until = n;
      } else if (arg == "--owner") {
        auto n = number(value);
        if (n > UINT32_MAX) {
          throw Error("UID out of range");
        }
        options.filter.owner = n;
      } else if (arg == "--every" || arg == "--keep" || arg == "--poll" || arg == "--runs") {
        if (command == "backup") {
          throw Error("Schedule option not valid for backup");
        }
        if ((arg == "--every" && command != "schedule") ||
            (arg == "--poll" && command != "watch")) {
          throw Error("Option not valid for this command: " + arg);
        }
        auto n = number(value);
        if (n > 8640000 || !n) {
          throw Error("Job option must be in 1..8640000");
        }
        if (arg == "--every") {
          schedule.interval_seconds = n;
        }
        if (arg == "--keep") {
          schedule.keep = n;
        }
        if (arg == "--poll") {
          schedule.poll_seconds = n;
        }
        if (arg == "--runs") {
          schedule.max_runs = n;
        }
      } else {
        throw Error("Unknown option: " + arg);
      }
    }
  }
  return parsed;
}
}  // namespace

int main(int argc, char** argv) {
  using namespace squirrel;
  try {
    if (argc == 1 || std::string(argv[1]) == "--help" || std::string(argv[1]) == "help") {
      help();
      return 0;
    }
    if (std::string(argv[1]) == "--version") {
      std::cout << "0.2.0\n";
      return 0;
    }
    std::string command = argv[1];
    const bool takesTwoPaths =
        command == "backup" || command == "restore" || command == "schedule" || command == "watch";
    if (!takesTwoPaths && command != "list" && command != "verify") {
      throw Error("Unknown command; use --help");
    }
    const int begin = takesTwoPaths ? 4 : 3;
    if (argc < begin) {
      throw Error("Missing path arguments; use --help");
    }
    const auto parsed = parseOptions(argc, argv, begin, command);
    const auto& options = parsed.backup;
    const auto& schedule = parsed.schedule;
    const bool quiet = parsed.quiet;
    auto log = [quiet](const std::string& line) {
      if (!quiet) {
        std::cerr << line << '\n';
      }
    };
    Summary summary;
    BackupService service;
    std::signal(SIGINT, onSignal);
    std::signal(SIGTERM, onSignal);
    Operation operation{&stopped, {}};
    if (command == "backup") {
      summary = service.backup(argv[2], argv[3], options, log, operation);
    } else if (command == "restore") {
      summary = service.restore(argv[2], argv[3], options.password, log, operation);
    } else if (command == "list" || command == "verify") {
      summary = service.inspect(argv[2], options.password, log, command == "list", operation);
      if (command == "list") {
        for (const auto& e : summary.items) {
          std::cout << typeName(e.type) << '\t' << e.size << '\t'
                    << std::quoted(e.path.empty() ? "." : e.path) << '\n';
        }
      }
    } else {
      Scheduler::run(argv[2], argv[3], options, schedule, stopped, log);
      return 0;
    }
    std::cout << "OK entries=" << summary.entries << " files=" << summary.files
              << " source_bytes=" << summary.bytes << " archive_bytes=" << summary.archive_bytes
              << '\n';
    return 0;
  } catch (const Cancelled&) {
    std::cerr << "Cancelled; incomplete output removed.\n";
    return 130;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
