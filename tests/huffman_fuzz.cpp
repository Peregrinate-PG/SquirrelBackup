// Copyright 2026 Squirrel Backup course project.
// Optional libFuzzer entry point: untrusted compressed bytes and encoder roundtrips.
#include <cstddef>
#include <cstdint>
#include <cstdlib>

#include "squirrel/backup.h"
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  using squirrel::Bytes;
  using squirrel::Error;
  using squirrel::HuffmanCodec;
  if (size < 4) {
    return 0;
  }
  uint32_t expected = 0;
  for (int i = 0; i < 4; ++i) {
    expected |= static_cast<uint32_t>(data[i]) << (8 * i);
  }
  expected %= 8193;
  Bytes input(data + 4, data + size);
  try {
    Bytes decoded = HuffmanCodec::decode(input, expected);
    if (HuffmanCodec::decode(HuffmanCodec::encode(decoded), expected) != decoded) {
      std::abort();
    }
  } catch (const Error&) {
  }
  if (input.size() < 8193 &&
      HuffmanCodec::decode(HuffmanCodec::encode(input), input.size()) != input) {
    std::abort();
  }
  return 0;
}
