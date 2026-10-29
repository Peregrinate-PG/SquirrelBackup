// Copyright 2026 Squirrel Backup course project.
#include <gtest/gtest.h>
#include <sys/xattr.h>

#include <fstream>
#include <random>
#include <string>

#include "internal.h"
#include "squirrel/backup.h"
namespace squirrel {
namespace {
TEST(Huffman, Empty) { EXPECT_EQ(HuffmanCodec::decode(HuffmanCodec::encode({}), 0), Bytes{}); }
TEST(Huffman, SingleSymbol) {
  Bytes data(10000, 65);
  EXPECT_EQ(HuffmanCodec::decode(HuffmanCodec::encode(data), data.size()), data);
}
TEST(Huffman, AllSymbols) {
  Bytes data;
  for (int i = 0; i < 256; ++i) {
    data.push_back(i);
  }
  EXPECT_EQ(HuffmanCodec::decode(HuffmanCodec::encode(data), data.size()), data);
}
TEST(Huffman, RandomRoundtrip) {
  std::mt19937 gen(42);
  for (size_t n : {1, 2, 17, 1024, 65537, 1048576}) {
    Bytes data(n);
    for (auto& c : data) {
      c = gen() & 255;
    }
    EXPECT_EQ(HuffmanCodec::decode(HuffmanCodec::encode(data), n), data);
  }
}
TEST(Huffman, Compression) {
  Bytes data(100000, 65);
  EXPECT_LT(HuffmanCodec::encode(data).size(), data.size() / 10);
}
TEST(Huffman, RejectTruncation) { EXPECT_THROW(HuffmanCodec::decode(Bytes(42), 10), Error); }
TEST(Huffman, RejectFrequency) {
  auto bytes = HuffmanCodec::encode(Bytes(100, 65));
  EXPECT_THROW(HuffmanCodec::decode(bytes, 99), Error);
}
TEST(Huffman, RejectOversize) { EXPECT_THROW(HuffmanCodec::encode(Bytes(kBlockSize + 1)), Error); }
TEST(Huffman, RejectTrailing) {
  auto bytes = HuffmanCodec::encode(Bytes(100, 65));
  bytes.push_back(0);
  EXPECT_THROW(HuffmanCodec::decode(bytes, 100), Error);
}
class BackupTest : public ::testing::Test {
 protected:
  TempDir temp;
  fs::path source = temp.path / "source", archive = temp.path / "backup.sqbk",
           restored = temp.path / "restored";
  BackupService service;
  void SetUp() override {
    fs::create_directories(source / "空目录");
    fs::create_directories(source / "nested");
    std::ofstream(source / "中文.txt") << "hello\n";
    std::ofstream(source / "empty");
    std::ofstream(source / "nested" / "large", std::ios::binary)
        << std::string(2 * kBlockSize + 17, 'a');
  }
  static std::string contents(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(in), {}};
  }
};
TEST_F(BackupTest, Roundtrip) {
  service.backup(source, archive);
  auto result = service.restore(archive, restored);
  EXPECT_EQ(result.files, 3ULL);
  EXPECT_TRUE(fs::is_directory(restored / "空目录"));
  EXPECT_EQ(contents(source / "中文.txt"), contents(restored / "中文.txt"));
  EXPECT_EQ(contents(source / "nested" / "large"), contents(restored / "nested" / "large"));
}
TEST_F(BackupTest, RawRoundtrip) {
  BackupOptions o;
  o.compress = false;
  service.backup(source, archive, o);
  service.restore(archive, restored);
  EXPECT_EQ(contents(source / "nested" / "large"), contents(restored / "nested" / "large"));
}
TEST_F(BackupTest, EncryptedRoundtrip) {
  BackupOptions o;
  o.password = "test-password-2026";
  service.backup(source, archive, o);
  EXPECT_THROW(service.inspect(archive), Error);
  service.restore(archive, restored, o.password);
  EXPECT_EQ(contents(restored / "中文.txt"), "hello\n");
}
TEST_F(BackupTest, WrongPasswordLeavesNoOutput) {
  BackupOptions o;
  o.password = "test-password-2026";
  service.backup(source, archive, o);
  EXPECT_THROW(service.restore(archive, restored, "bad-password"), Error);
  EXPECT_FALSE(fs::exists(restored));
}
TEST_F(BackupTest, RejectShortPassword) {
  BackupOptions o;
  o.password = "123";
  EXPECT_THROW(service.backup(source, archive, o), Error);
  EXPECT_FALSE(fs::exists(archive));
}
TEST_F(BackupTest, TamperDetection) {
  service.backup(source, archive);
  std::fstream file(archive, std::ios::in | std::ios::out | std::ios::binary);
  file.seekp(55);
  file.put('!');
  file.close();
  EXPECT_THROW(service.restore(archive, restored), Error);
  EXPECT_FALSE(fs::exists(restored));
}
TEST_F(BackupTest, RejectTruncated) {
  service.backup(source, archive);
  fs::resize_file(archive, 20);
  EXPECT_THROW(service.inspect(archive), Error);
}
TEST_F(BackupTest, NoOverwriteBackup) {
  service.backup(source, archive);
  auto original = contents(archive);
  EXPECT_THROW(service.backup(source, archive), Error);
  EXPECT_EQ(contents(archive), original);
}
TEST_F(BackupTest, NoOverwriteRestore) {
  service.backup(source, archive);
  fs::create_directory(restored);
  std::ofstream(restored / "keep") << "keep";
  EXPECT_THROW(service.restore(archive, restored), Error);
  EXPECT_EQ(contents(restored / "keep"), "keep");
}
TEST_F(BackupTest, RejectOutputInSource) {
  EXPECT_THROW(service.backup(source, source / "bad.sqbk"), Error);
}
TEST_F(BackupTest, MissingSource) {
  EXPECT_THROW(service.backup(temp.path / "missing", archive), std::exception);
}
TEST_F(BackupTest, SymlinkHardlinkFifo) {
  fs::create_symlink("中文.txt", source / "sym");
  fs::create_symlink("missing", source / "broken");
  fs::create_hard_link(source / "中文.txt", source / "hard");
  ASSERT_EQ(::mkfifo((source / "pipe").c_str(), 0600), 0);
  service.backup(source, archive);
  service.restore(archive, restored);
  EXPECT_EQ(fs::read_symlink(restored / "sym"), fs::path("中文.txt"));
  EXPECT_TRUE(fs::is_symlink(restored / "broken"));
  EXPECT_TRUE(fs::equivalent(restored / "hard", restored / "中文.txt"));
  struct stat st {};
  ASSERT_EQ(::lstat((restored / "pipe").c_str(), &st), 0);
  EXPECT_TRUE(S_ISFIFO(st.st_mode));
}
TEST_F(BackupTest, Metadata) {
  auto path = source / "中文.txt";
  ASSERT_EQ(::chmod(path.c_str(), 0640), 0);
  struct timespec times[2] = {{1600000000, 123456789}, {1600000100, 987654321}};
  ASSERT_EQ(::utimensat(AT_FDCWD, path.c_str(), times, 0), 0);
  ASSERT_EQ(::setxattr(path.c_str(), "user.squirrel", "value", 5, 0, 0), 0);
  service.backup(source, archive);
  service.restore(archive, restored);
  struct stat st {};
  ASSERT_EQ(::stat((restored / "中文.txt").c_str(), &st), 0);
  EXPECT_EQ(st.st_mode & 0777, 0640);
  EXPECT_EQ(st.st_mtimespec.tv_sec, times[1].tv_sec);
  EXPECT_EQ(st.st_mtimespec.tv_nsec, times[1].tv_nsec);
  EXPECT_EQ(st.st_atimespec.tv_sec, times[0].tv_sec);
  char attr[5];
  EXPECT_EQ(::getxattr((restored / "中文.txt").c_str(), "user.squirrel", attr, 5, 0, 0), 5);
  EXPECT_EQ(std::string(attr, 5), "value");
}
TEST_F(BackupTest, ReadOnlyRootRestoresWithOriginalPermissions) {
  ASSERT_EQ(::chmod(source.c_str(), 0555), 0);
  service.backup(source, archive);
  service.restore(archive, restored);
  EXPECT_EQ(contents(restored / "中文.txt"), "hello\n");
  struct stat st {};
  ASSERT_EQ(::lstat(restored.c_str(), &st), 0);
  EXPECT_EQ(st.st_mode & 0777, 0555);
}
TEST_F(BackupTest, RewritePreservingMtimeIsRejected) {
  const auto file = source / "中文.txt";
  bool changed = false;
  Log log = [&](const std::string& line) {
    if (line.find("Scanned ") == 0) {
      struct stat before {};
      ASSERT_EQ(::stat(file.c_str(), &before), 0);
      ::usleep(1000);                    // Ensure distinct ctime even on a fast temporary volume.
      std::ofstream(file) << "other\n";  // Same length as the original file.
      struct timespec times[2] = {before.st_atimespec, before.st_mtimespec};
      ASSERT_EQ(::utimensat(AT_FDCWD, file.c_str(), times, 0), 0);
      changed = true;
    }
  };
  EXPECT_THROW(service.backup(source, archive, {}, log), Error);
  EXPECT_TRUE(changed);
  EXPECT_FALSE(fs::exists(archive));
}
TEST_F(BackupTest, PrivateCleanupHandlesUnreadableDirectoriesWithoutFollowingSymlinks) {
  const auto external = source / "external";
  fs::create_directory(external);
  std::ofstream(external / "keep") << "preserve";
  ASSERT_EQ(::chmod(external.c_str(), 0500), 0);
  fs::path private_path;
  {
    TempDir private_dir(temp.path);
    private_path = private_dir.path;
    fs::create_directory(private_path / "locked");
    std::ofstream(private_path / "locked" / "secret") << "decrypted data";
    fs::create_symlink(external, private_path / "link");
    ASSERT_EQ(::chmod((private_path / "locked").c_str(), 0000), 0);
  }
  EXPECT_FALSE(fs::exists(private_path));
  EXPECT_EQ(contents(external / "keep"), "preserve");
  struct stat st {};
  ASSERT_EQ(::lstat(external.c_str(), &st), 0);
  EXPECT_EQ(st.st_mode & 0777, 0500);
}
TEST_F(BackupTest, FailedPublicationCleansReadOnlyRestoredDirectories) {
  ASSERT_EQ(::chmod((source / "nested").c_str(), 0500), 0);
  auto entries = FileScanner::scan(source, {});
  // A foreign owner produces a deterministic warning while restoring root metadata.
  entries.front().uid = static_cast<uint32_t>(::getuid()) + 1;
  const auto tree = temp.path / "tree";
  ArchiveWriter::write(source, entries, tree, true, {});
  CryptoEnvelope::seal(tree, archive, "");
  bool raced = false;
  Log log = [&](const std::string& line) {
    if (line.find("WARNING: owner/group not restored: ") == 0) {
      fs::create_directory(restored);
      std::ofstream(restored / "keep") << "concurrent destination";
      raced = true;
    }
  };
  EXPECT_THROW(service.restore(archive, restored, "", log), Error);
  EXPECT_TRUE(raced);
  EXPECT_EQ(contents(restored / "keep"), "concurrent destination");
  for (const auto& child : fs::directory_iterator(temp.path)) {
    EXPECT_NE(child.path().filename().string().find(".squirrel-"), 0U);
  }
}
TEST_F(BackupTest, ExcludePrunesDirectory) {
  BackupOptions o;
  o.filter.excludes = {"nested"};
  service.backup(source, archive, o);
  service.restore(archive, restored);
  EXPECT_FALSE(fs::exists(restored / "nested"));
}
TEST_F(BackupTest, NameFilter) {
  BackupOptions o;
  o.filter.name_pattern = "*.txt";
  auto result = service.backup(source, archive, o);
  EXPECT_EQ(result.files, 1ULL);
}
TEST_F(BackupTest, PathFilter) {
  BackupOptions o;
  o.filter.path_pattern = "nested/*";
  EXPECT_EQ(service.backup(source, archive, o).files, 1ULL);
}
TEST_F(BackupTest, SizeFilter) {
  BackupOptions o;
  o.filter.min_size = 1;
  o.filter.max_size = 10;
  EXPECT_EQ(service.backup(source, archive, o).files, 1ULL);
}
TEST_F(BackupTest, TimeFilter) {
  BackupOptions o;
  o.filter.until = 1;
  EXPECT_EQ(service.backup(source, archive, o).files, 0ULL);
}
TEST_F(BackupTest, OwnerFilter) {
  BackupOptions o;
  o.filter.owner = ::getuid();
  EXPECT_EQ(service.backup(source, archive, o).files, 3ULL);
}
TEST_F(BackupTest, TypeFilter) {
  fs::create_symlink("中文.txt", source / "link");
  BackupOptions o;
  o.filter.types = "l";
  service.backup(source, archive, o);
  auto result = service.inspect(archive);
  EXPECT_EQ(result.files, 0ULL);
  EXPECT_EQ(result.entries, 4ULL);
}
TEST_F(BackupTest, InvalidFilter) {
  BackupOptions o;
  o.filter.min_size = 20;
  o.filter.max_size = 10;
  EXPECT_THROW(service.backup(source, archive, o), Error);
}
TEST_F(BackupTest, EmptyTree) {
  fs::remove_all(source);
  fs::create_directory(source);
  EXPECT_EQ(service.backup(source, archive).entries, 1ULL);
  service.restore(archive, restored);
  EXPECT_TRUE(fs::is_empty(restored));
}
TEST_F(BackupTest, UncompressedEncrypted) {
  BackupOptions o;
  o.compress = false;
  o.password = "password0123";
  service.backup(source, archive, o);
  service.restore(archive, restored, o.password);
  EXPECT_EQ(contents(source / "nested" / "large"), contents(restored / "nested" / "large"));
}
TEST_F(BackupTest, RetentionFailureDoesNotRepeatSnapshot) {
  auto repo = temp.path / "repository";
  fs::create_directory(repo);
  ScheduleOptions schedule;
  schedule.interval_seconds = 1;
  schedule.keep = 1;
  schedule.max_runs = 2;
  std::atomic<bool> stop{false};
  int published = 0;
  bool warned = false;
  fs::path job;
  Log log = [&](const std::string& line) {
    if (line.find("Job repository: ") == 0) {
      job = line.substr(16);
    }
    if (line.find("Backup complete: ") == 0) {
      ++published;
      if (published == 2) {
        auto old = job / "snapshot-1.sqbk";
        fs::remove(old);
        fs::create_directory(old);
        std::ofstream(old / "cannot-remove-as-file") << "retention failure fixture";
      }
      if (published >= 3) {
        stop.store(true);  // Bounds the regression even for broken code.
      }
    }
    if (line.find("WARNING: retention cleanup failed") == 0) {
      warned = true;
    }
  };
  Scheduler::run(source, repo, {}, schedule, stop, log);
  EXPECT_EQ(published, 2);
  EXPECT_TRUE(warned);
  EXPECT_TRUE(fs::is_regular_file(job / "snapshot-2.sqbk"));
  EXPECT_EQ(service.inspect(job / "snapshot-2.sqbk").files, 3ULL);
}
class CancelBackupTest : public BackupTest, public ::testing::WithParamInterface<Phase> {};
TEST_P(CancelBackupTest, LeavesNoPublishedOrTemporaryFiles) {
  std::atomic<bool> stop{false};
  BackupOptions options;
  options.compress = false;
  options.password = "cancellation-test";
  bool reached = false;
  Operation operation{
      &stop, [&](const ProgressInfo& info) {
        bool in_block = info.phase == Phase::Pack || info.phase == Phase::Seal;
        if (info.phase == GetParam() && (!in_block || info.completed >= kBlockSize)) {
          reached = true;
          stop.store(true);
        }
      }};
  EXPECT_THROW(service.backup(source, archive, options, {}, operation), Cancelled);
  EXPECT_TRUE(reached);
  EXPECT_FALSE(fs::exists(archive));
  for (const auto& child : fs::directory_iterator(temp.path)) {
    EXPECT_EQ(child.path(), source);
  }
  EXPECT_EQ(contents(source / "中文.txt"), "hello\n");
}
INSTANTIATE_TEST_SUITE_P(EachStage, CancelBackupTest,
                         ::testing::Values(Phase::Scan, Phase::Pack, Phase::Seal,
                                           Phase::CheckSource, Phase::Publish));

class CancelRestoreTest : public BackupTest, public ::testing::WithParamInterface<Phase> {};
TEST_P(CancelRestoreTest, LeavesNoDestinationAndPreservesArchive) {
  BackupOptions options;
  options.compress = false;
  options.password = "cancellation-test";
  ASSERT_EQ(::chmod(source.c_str(), 0555), 0);
  service.backup(source, archive, options);
  const auto original = contents(archive);
  std::atomic<bool> stop{false};
  bool reached = false;
  Operation operation{
      &stop, [&](const ProgressInfo& info) {
        bool in_block = info.phase == Phase::Authenticate || info.phase == Phase::Decode ||
                        info.phase == Phase::Read;
        if (info.phase == GetParam() && (!in_block || info.completed >= kBlockSize)) {
          reached = true;
          stop.store(true);
        }
      }};
  EXPECT_THROW(service.restore(archive, restored, options.password, {}, operation), Cancelled);
  EXPECT_TRUE(reached);
  EXPECT_FALSE(fs::exists(restored));
  EXPECT_EQ(contents(archive), original);
  for (const auto& child : fs::directory_iterator(temp.path)) {
    EXPECT_TRUE(child.path() == source || child.path() == archive);
  }
}
INSTANTIATE_TEST_SUITE_P(EachStage, CancelRestoreTest,
                         ::testing::Values(Phase::Authenticate, Phase::Decode, Phase::Read,
                                           Phase::Metadata, Phase::Publish));

TEST_F(BackupTest, SourceAdditionAfterPackingPreventsPublication) {
  Operation operation{nullptr, [&](const ProgressInfo& info) {
                        if (info.phase == Phase::CheckSource) {
                          std::ofstream(source / "late-file") << "created during backup";
                        }
                      }};
  EXPECT_THROW(service.backup(source, archive, {}, {}, operation), Error);
  EXPECT_FALSE(fs::exists(archive));
}
TEST_F(BackupTest, SourceDeletionAfterPackingPreventsPublication) {
  Operation operation{nullptr, [&](const ProgressInfo& info) {
                        if (info.phase == Phase::CheckSource) {
                          fs::remove(source / "empty");
                        }
                      }};
  EXPECT_THROW(service.backup(source, archive, {}, {}, operation), Error);
  EXPECT_FALSE(fs::exists(archive));
}
TEST_F(BackupTest, SourceMetadataChangeAfterPackingPreventsPublication) {
  Operation operation{nullptr, [&](const ProgressInfo& info) {
                        if (info.phase == Phase::CheckSource) {
                          ASSERT_EQ(::chmod((source / "nested").c_str(), 0500), 0);
                        }
                      }};
  EXPECT_THROW(service.backup(source, archive, {}, {}, operation), Error);
  EXPECT_FALSE(fs::exists(archive));
}
TEST_F(BackupTest, CancelledJobKeepsPreviousSnapshot) {
  auto repo = temp.path / "repository";
  fs::create_directory(repo);
  ScheduleOptions schedule;
  schedule.interval_seconds = 1;
  schedule.keep = 1;
  schedule.max_runs = 2;
  std::atomic<bool> stop{false};
  int published = 0;
  fs::path first;
  Log log = [&](const std::string& line) {
    if (line.find("Backup complete: ") == 0) {
      ++published;
      first = line.substr(17);
    }
  };
  Progress progress = [&](const ProgressInfo& info) {
    if (published == 1 && info.phase == Phase::Pack && info.completed >= kBlockSize) {
      stop.store(true);
    }
  };
  EXPECT_NO_THROW(Scheduler::run(source, repo, {}, schedule, stop, log, progress));
  EXPECT_TRUE(stop.load());
  EXPECT_EQ(published, 1);
  ASSERT_TRUE(fs::is_regular_file(first));
  EXPECT_EQ(service.inspect(first).files, 3ULL);
  for (const auto& child : fs::directory_iterator(first.parent_path())) {
    EXPECT_EQ(child.path(), first);
  }
}
TEST_F(BackupTest, PreCancelledOperationDoesNotTouchFilesystem) {
  std::atomic<bool> stop{true};
  Operation operation{&stop, {}};
  EXPECT_THROW(service.backup("missing", archive, {}, {}, operation), Cancelled);
  EXPECT_THROW(service.restore("missing", restored, "", {}, operation), Cancelled);
  EXPECT_THROW(service.inspect("missing", "", {}, true, operation), Cancelled);
  EXPECT_FALSE(fs::exists(archive));
  EXPECT_FALSE(fs::exists(restored));
}
}  // namespace
}  // namespace squirrel
