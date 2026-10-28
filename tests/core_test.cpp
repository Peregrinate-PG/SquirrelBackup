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
  struct stat st{};
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
  struct stat st{};
  ASSERT_EQ(::stat((restored / "中文.txt").c_str(), &st), 0);
  EXPECT_EQ(st.st_mode & 0777, 0640);
  EXPECT_EQ(st.st_mtimespec.tv_sec, times[1].tv_sec);
  EXPECT_EQ(st.st_mtimespec.tv_nsec, times[1].tv_nsec);
  EXPECT_EQ(st.st_atimespec.tv_sec, times[0].tv_sec);
  char attr[5];
  EXPECT_EQ(::getxattr((restored / "中文.txt").c_str(), "user.squirrel", attr, 5, 0, 0), 5);
  EXPECT_EQ(std::string(attr, 5), "value");
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
}  // namespace
}  // namespace squirrel
