// Copyright 2026 Squirrel Backup course project.
#include <array>
#include <functional>
#include <queue>
#include <tuple>
#include <utility>
#include <vector>

#include "squirrel/backup.h"

namespace squirrel {
namespace {
struct Node {
  uint64_t weight;
  int symbol, left, right;
};
struct Tree {
  std::vector<Node> nodes;
  int root = -1;
  explicit Tree(const std::array<uint32_t, 256>& freq) {
    // Index is the deterministic tie breaker. Encoder and decoder build identically.
    using Item = std::pair<uint64_t, int>;
    std::priority_queue<Item, std::vector<Item>, std::greater<Item>> queue;
    for (int i = 0; i < 256; ++i) {
      if (freq[i]) {
        nodes.push_back({freq[i], i, -1, -1});
        queue.push({freq[i], static_cast<int>(nodes.size()) - 1});
      }
    }
    while (queue.size() > 1) {
      auto a = queue.top();
      queue.pop();
      auto b = queue.top();
      queue.pop();
      nodes.push_back({a.first + b.first, -1, a.second, b.second});
      queue.push({a.first + b.first, static_cast<int>(nodes.size()) - 1});
    }
    if (!queue.empty()) {
      root = queue.top().second;
    }
  }
  void codes(int n, std::vector<bool> prefix, std::array<std::vector<bool>, 256>* out) const {
    if (nodes[n].symbol >= 0) {
      (*out)[nodes[n].symbol] = prefix;
      return;
    }
    prefix.push_back(false);
    codes(nodes[n].left, prefix, out);
    prefix.back() = true;
    codes(nodes[n].right, prefix, out);
  }
};
}  // namespace
Bytes HuffmanCodec::encode(const Bytes& input) {
  if (input.size() > kBlockSize) {
    throw Error("Huffman block too large");
  }
  std::array<uint32_t, 256> freq{};
  for (auto byte : input) {
    ++freq[byte];
  }
  Bytes out;
  for (auto n : freq) {
    for (int i = 0; i < 4; ++i) {
      out.push_back((n >> (8 * i)) & 255);
    }
  }
  Tree tree(freq);
  if (tree.root < 0) {
    return out;
  }
  std::array<std::vector<bool>, 256> codes;
  tree.codes(tree.root, {}, &codes);
  uint8_t byte = 0;
  int bits = 0;
  for (auto c : input) {
    for (bool bit : codes[c]) {
      byte = static_cast<uint8_t>((byte << 1) | bit);
      if (++bits == 8) {
        out.push_back(byte);
        bits = 0;
        byte = 0;
      }
    }
  }
  if (bits) {
    out.push_back(static_cast<uint8_t>(byte << (8 - bits)));
  }
  return out;
}

Bytes HuffmanCodec::decode(const Bytes& input, uint32_t expected) {
  if (expected > kBlockSize || input.size() < 1024 || input.size() > kBlockSize + 1024) {
    throw Error("Invalid Huffman block length");
  }
  std::array<uint32_t, 256> freq{};
  uint64_t total = 0;
  for (int i = 0; i < 256; ++i) {
    for (int j = 0; j < 4; ++j) {
      freq[i] |= static_cast<uint32_t>(input[i * 4 + j]) << (8 * j);
    }
    total += freq[i];
  }
  if (total != expected) {
    throw Error("Huffman frequency sum mismatch");
  }
  Tree tree(freq);
  Bytes out;
  out.reserve(expected);
  if (!expected) {
    if (input.size() != 1024) {
      throw Error("Trailing empty Huffman data");
    }
    return out;
  }
  if (tree.nodes[tree.root].symbol >= 0) {
    if (input.size() != 1024) {
      throw Error("Trailing single-symbol Huffman data");
    }
    out.assign(expected, tree.nodes[tree.root].symbol);
    return out;
  }
  size_t bit = 8192;
  std::array<uint32_t, 256> observed{};
  while (out.size() < expected) {
    int n = tree.root;
    while (tree.nodes[n].symbol < 0) {
      if (bit >= input.size() * 8) {
        throw Error("Truncated Huffman data");
      }
      bool b = (input[bit / 8] >> (7 - bit % 8)) & 1;
      ++bit;
      n = b ? tree.nodes[n].right : tree.nodes[n].left;
    }
    auto c = static_cast<uint8_t>(tree.nodes[n].symbol);
    out.push_back(c);
    ++observed[c];
  }
  if ((bit + 7) / 8 != input.size() || observed != freq) {
    throw Error("Invalid Huffman payload");
  }
  for (; bit < input.size() * 8; ++bit) {
    if ((input[bit / 8] >> (7 - bit % 8)) & 1) {
      throw Error("Invalid Huffman padding");
    }
  }
  return out;
}
}  // namespace squirrel
