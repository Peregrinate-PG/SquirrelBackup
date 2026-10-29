// Copyright 2026 Squirrel Backup course project.
#include <fcntl.h>
#include <unistd.h>

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "squirrel/backup.h"

namespace {
int input_fd = -1;
std::filesystem::path input_path;

void cleanup() {
  if (input_fd >= 0) {
    ::close(input_fd);
  }
  if (!input_path.empty()) {
    ::unlink(input_path.c_str());
  }
}

void requireHarness(bool ok) {
  if (!ok) {
    std::perror("fuzz harness I/O failure");
    std::abort();
  }
}
}  // namespace

extern "C" int LLVMFuzzerInitialize(int* argc, char*** argv) {
  (void)argc;
  (void)argv;
  const char* directory = std::getenv("SQUIRREL_FUZZ_DIRECTORY");
  requireHarness(directory != nullptr);
  std::string pattern = (std::filesystem::path(directory) / ".tree-input-XXXXXX").string();
  std::vector<char> name(pattern.begin(), pattern.end());
  name.push_back(0);
  input_fd = ::mkstemp(name.data());
  requireHarness(input_fd >= 0);
  input_path = name.data();
  std::atexit(cleanup);
  return 0;
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  requireHarness(::ftruncate(input_fd, 0) == 0 && ::lseek(input_fd, 0, SEEK_SET) == 0);
  size_t offset = 0;
  while (offset < size) {
    ssize_t count = ::write(input_fd, data + offset, size - offset);
    if (count < 0 && errno == EINTR) {
      continue;
    }
    requireHarness(count > 0);
    offset += static_cast<size_t>(count);
  }
  try {
    // Parse SQTREE directly so outer authentication does not reject mutations first.
    // A null destination prevents restoration or any writes derived from input paths.
    squirrel::ArchiveReader::read(input_path, nullptr, {}, size % 2 != 0);
  } catch (const squirrel::Error&) {
    // Explicit input-validation failures are expected; other exceptions are not masked.
  }
  return 0;
}
