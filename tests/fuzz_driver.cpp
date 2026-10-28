// Copyright 2026 Squirrel Backup course project.
// Bounded deterministic mutation testing when the SDK lacks libFuzzer.
#include <chrono>
#include <fstream>
#include <random>
#include <string>
#include <utility>
#include <vector>

#include "squirrel/backup.h"
extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size);
int main(int argc, char** argv) {
  if (argc != 3) {
    return 2;
  }
  const int seconds = std::stoi(argv[2]);
  if (seconds < 1 || seconds > 600) {
    return 2;
  }
  using squirrel::Bytes;
  using squirrel::HuffmanCodec;
  std::mt19937 random(20261029);
  std::vector<Bytes> corpus;
  for (uint32_t n : {0, 1, 17, 1024, 4096}) {
    for (bool repeated : {true, false}) {
      Bytes raw(n);
      for (auto& c : raw) {
        c = repeated ? 65 : random() & 255;
      }
      Bytes packed(4);
      for (int i = 0; i < 4; ++i) {
        packed[i] = (n >> (8 * i)) & 255;
      }
      auto payload = HuffmanCodec::encode(raw);
      packed.insert(packed.end(), payload.begin(), payload.end());
      corpus.push_back(std::move(packed));
    }
  }
  const auto start = std::chrono::steady_clock::now();
  uint64_t count = 0;
  while (std::chrono::steady_clock::now() - start < std::chrono::seconds(seconds)) {
    Bytes data = corpus[random() % corpus.size()];
    if (count % 3 == 0) {
      for (unsigned i = 0, n = random() % 12 + 1; i < n; ++i) {
        data[random() % data.size()] ^= 1 << (random() % 8);
      }
    } else if (count % 3 == 1) {
      data.resize(random() % 8193);
      for (auto& c : data) {
        c = random() & 255;
      }
    }
    LLVMFuzzerTestOneInput(data.data(), data.size());
    ++count;
  }
  auto duration = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
  std::ofstream(argv[1]) << "{\"passed\":true,\"iterations\":" << count
                         << ",\"seconds\":" << duration
                         << ",\"seed\":20261029,\"coverage_guided\":false}";
}
