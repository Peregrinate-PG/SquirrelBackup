// Copyright 2026 Squirrel Backup course project.
#include <CommonCrypto/CommonCryptor.h>
#include <CommonCrypto/CommonDigest.h>
#include <CommonCrypto/CommonHMAC.h>
#include <CommonCrypto/CommonKeyDerivation.h>
#include <Security/SecRandom.h>

#include <algorithm>
#include <array>
#include <memory>
#include <string>

#include "internal.h"

namespace squirrel {
namespace {
constexpr size_t kHeaderSize = 44, kTagSize = 32;
constexpr uint32_t kRounds = 200000;
using Key = std::array<uint8_t, 64>;
Key derive(const std::string& password, const Bytes& header) {
  Key key{};
  require(CCKeyDerivationPBKDF(kCCPBKDF2, password.data(), password.size(), header.data() + 12, 16,
                               kCCPRFHmacAlgSHA256, kRounds, key.data(), key.size()) == kCCSuccess,
          "Password key derivation failed");
  return key;
}

struct Digest {
  bool encrypted;
  CC_SHA256_CTX sha{};
  CCHmacContext hmac{};
  Digest(bool enc, const Key& key) : encrypted(enc) {
    if (enc) {
      CCHmacInit(&hmac, kCCHmacAlgSHA256, key.data() + 32, 32);
    } else {
      CC_SHA256_Init(&sha);
    }
  }
  void update(const void* p, size_t n) {
    if (encrypted) {
      CCHmacUpdate(&hmac, p, n);
    } else {
      CC_SHA256_Update(&sha, p, static_cast<CC_LONG>(n));
    }
  }
  std::array<uint8_t, 32> finish() {
    std::array<uint8_t, 32> tag{};
    if (encrypted) {
      CCHmacFinal(&hmac, tag.data());
    } else {
      CC_SHA256_Final(tag.data(), &sha);
    }
    return tag;
  }
};
struct Cipher {
  CCCryptorRef ref = nullptr;
  Cipher(CCOperation op, const Key& key, const Bytes& header) {
    require(CCCryptorCreate(op, kCCAlgorithmAES, kCCOptionPKCS7Padding, key.data(), 32,
                            header.data() + 28, &ref) == kCCSuccess,
            "Cannot initialize AES");
  }
  Cipher(const Cipher&) = delete;
  Cipher& operator=(const Cipher&) = delete;

  ~Cipher() {
    if (ref) {
      CCCryptorRelease(ref);
    }
  }
};
void write(std::ostream& stream, const void* p, size_t n) {
  stream.write(static_cast<const char*>(p), n);
  require(static_cast<bool>(stream), "Cannot write envelope (disk full?)");
}
}  // namespace
void CryptoEnvelope::seal(const fs::path& plain, const fs::path& output,
                          const std::string& password, const Operation& operation) {
  const auto total = fs::file_size(plain);
  uint64_t completed = 0;
  operation.checkpoint(Phase::Seal, completed, total);
  bool encrypted = !password.empty();
  Bytes header(kHeaderSize, 0);
  const std::string magic = "SQBK0001";
  std::copy(magic.begin(), magic.end(), header.begin());
  header[8] = encrypted ? 1 : 0;
  if (encrypted) {
    require(SecRandomCopyBytes(kSecRandomDefault, 32, header.data() + 12) == errSecSuccess,
            "Secure random generator failed");
  }
  Key key{};
  if (encrypted) {
    key = derive(password, header);
  }
  Digest digest(encrypted, key);
  digest.update(header.data(), header.size());
  std::unique_ptr<Cipher> cipher;
  if (encrypted) {
    cipher = std::make_unique<Cipher>(kCCEncrypt, key, header);
  }
  std::ifstream in(plain, std::ios::binary);
  require(static_cast<bool>(in), "Cannot open packed data");
  privateFile(output);
  std::ofstream out(output, std::ios::binary);
  write(out, header.data(), header.size());
  Bytes buffer(kBlockSize), transformed(kBlockSize + 32);
  while (in) {
    operation.checkpoint(Phase::Seal, completed, total);
    in.read(reinterpret_cast<char*>(buffer.data()), buffer.size());
    size_t n = in.gcount();
    if (!n) {
      break;
    }
    const uint8_t* data = buffer.data();
    size_t count = n;
    if (encrypted) {
      require(CCCryptorUpdate(cipher->ref, buffer.data(), n, transformed.data(), transformed.size(),
                              &count) == kCCSuccess,
              "AES encryption failed");
      data = transformed.data();
    }
    digest.update(data, count);
    write(out, data, count);
    completed += n;
  }
  require(in.eof() && !in.bad(), "Cannot read packed data");
  if (encrypted) {
    size_t count = 0;
    require(
        CCCryptorFinal(cipher->ref, transformed.data(), transformed.size(), &count) == kCCSuccess,
        "AES finalization failed");
    digest.update(transformed.data(), count);
    write(out, transformed.data(), count);
  }
  auto tag = digest.finish();
  write(out, tag.data(), tag.size());
  out.close();
  require(static_cast<bool>(out), "Cannot finish envelope");
  std::fill(key.begin(), key.end(), 0);
  operation.checkpoint(Phase::Seal, completed, total);
}

void CryptoEnvelope::open(const fs::path& archive, const fs::path& plain,
                          const std::string& password, const Operation& operation) {
  operation.checkpoint(Phase::Authenticate);
  // Authenticate and decode through the same descriptor to prevent path replacement.
  Fd fd(::open(archive.c_str(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK));
  syscheck(fd.value >= 0, "Cannot open backup");
  struct stat before {};
  syscheck(::fstat(fd.value, &before) == 0, "Cannot stat backup");
  require(S_ISREG(before.st_mode) && before.st_size >= static_cast<int64_t>(kHeaderSize + kTagSize),
          "Not a valid backup file");
  auto exact = [&](void* data, size_t n) {
    size_t off = 0;
    while (off < n) {
      ssize_t got = ::read(fd.value, static_cast<char*>(data) + off, n - off);
      if (got < 0 && errno == EINTR) {
        continue;
      }
      require(got > 0, "Truncated or unreadable backup");
      off += got;
    }
  };
  Bytes header(kHeaderSize);
  exact(header.data(), header.size());
  require(std::string(header.begin(), header.begin() + 8) == "SQBK0001" && header[8] <= 1 &&
              !header[9] && !header[10] && !header[11],
          "Unknown backup format or version");
  bool encrypted = header[8] == 1;
  require(!encrypted || !password.empty(), "This backup requires a password");
  Key key{};
  if (encrypted) {
    key = derive(password, header);
  }
  Digest digest(encrypted, key);
  digest.update(header.data(), header.size());
  uint64_t payload = before.st_size - kHeaderSize - kTagSize, remaining = payload;
  Bytes buffer(kBlockSize), transformed(kBlockSize + 32);
  while (remaining) {
    operation.checkpoint(Phase::Authenticate, payload - remaining, payload);
    size_t n = std::min<uint64_t>(remaining, buffer.size());
    exact(buffer.data(), n);
    digest.update(buffer.data(), n);
    remaining -= n;
  }
  std::array<uint8_t, 32> stored{};
  exact(stored.data(), stored.size());
  auto actual = digest.finish();
  uint8_t difference = 0;
  for (size_t i = 0; i < stored.size(); ++i) {
    difference |= stored[i] ^ actual[i];
  }
  require(difference == 0, encrypted ? "Wrong password or damaged backup (authentication failed)"
                                     : "Backup checksum mismatch");
  operation.checkpoint(Phase::Authenticate, payload, payload);
  syscheck(::lseek(fd.value, kHeaderSize, SEEK_SET) == static_cast<int64_t>(kHeaderSize),
           "Cannot seek backup");
  std::unique_ptr<Cipher> cipher;
  if (encrypted) {
    cipher = std::make_unique<Cipher>(kCCDecrypt, key, header);
  }
  privateFile(plain);
  std::ofstream out(plain, std::ios::binary);
  // Recompute the digest while decoding, detecting in-place writes between the two passes.
  Digest second(encrypted, key);
  second.update(header.data(), header.size());
  remaining = payload;
  while (remaining) {
    operation.checkpoint(Phase::Decode, payload - remaining, payload);
    size_t n = std::min<uint64_t>(remaining, buffer.size());
    exact(buffer.data(), n);
    second.update(buffer.data(), n);
    remaining -= n;
    const uint8_t* data = buffer.data();
    size_t count = n;
    if (encrypted) {
      require(CCCryptorUpdate(cipher->ref, data, n, transformed.data(), transformed.size(),
                              &count) == kCCSuccess,
              "AES decryption failed");
      data = transformed.data();
    }
    write(out, data, count);
  }
  require(second.finish() == actual, "Backup changed while reading");
  if (encrypted) {
    size_t count = 0;
    require(
        CCCryptorFinal(cipher->ref, transformed.data(), transformed.size(), &count) == kCCSuccess,
        "Invalid encrypted payload");
    write(out, transformed.data(), count);
  }
  struct stat after {};
  syscheck(::fstat(fd.value, &after) == 0, "Cannot stat backup");
  require(before.st_size == after.st_size &&
              before.st_mtimespec.tv_sec == after.st_mtimespec.tv_sec &&
              before.st_mtimespec.tv_nsec == after.st_mtimespec.tv_nsec,
          "Backup changed while reading");
  out.close();
  require(static_cast<bool>(out), "Cannot write decoded backup");
  std::fill(key.begin(), key.end(), 0);
  operation.checkpoint(Phase::Decode, payload, payload);
}
}  // namespace squirrel
