// Copyright 2026 Squirrel Backup course project.
#include "gui_support.h"

#include <sstream>

namespace squirrel::ui {
std::string previewDirectory;
std::string selfTestDirectory;
int previewPage = 0;

NSColor* accent() { return [NSColor colorWithSRGBRed:0.84 green:0.36 blue:0.16 alpha:1]; }
NSString* toNSString(const std::string& s) {
  NSString* value = [[NSString alloc] initWithBytes:s.data()
                                             length:s.size()
                                           encoding:NSUTF8StringEncoding];
  return value ? value : @"[非 UTF-8 文件名]";
}
std::string toString(NSString* s) {
  const char* value = s.UTF8String;
  return value ? value : "";
}
NSTextField* makeLabel(NSView* parent, NSString* text, NSRect frame, CGFloat size, BOOL bold) {
  NSTextField* l = [NSTextField labelWithString:text];
  l.frame = frame;
  l.font = bold ? [NSFont boldSystemFontOfSize:size] : [NSFont systemFontOfSize:size];
  l.textColor = NSColor.labelColor;
  [parent addSubview:l];
  return l;
}
NSTextField* makeInput(NSView* parent, NSString* placeholder, NSRect frame, BOOL secure) {
  NSTextField* f = secure ? [[NSSecureTextField alloc] initWithFrame:frame]
                          : [[NSTextField alloc] initWithFrame:frame];
  f.placeholderString = placeholder;
  f.font = [NSFont systemFontOfSize:13];
  f.bezelStyle = NSTextFieldRoundedBezel;
  [parent addSubview:f];
  return f;
}
NSButton* makeButton(NSView* parent, NSString* title, NSRect frame, id target, SEL action,
                     BOOL primary) {
  NSButton* b = [NSButton buttonWithTitle:title target:target action:action];
  b.frame = frame;
  b.bezelStyle = NSBezelStyleRounded;
  b.font = [NSFont systemFontOfSize:13 weight:NSFontWeightMedium];
  if (primary) {
    b.bezelColor = accent();
    b.keyEquivalent = @"\r";
  }
  [parent addSubview:b];
  return b;
}
bool parsePositiveInteger(NSString* text, uint32_t maximum, uint32_t& result) {
  auto value = toString(text);
  if (value.empty()) {
    return false;
  }
  uint32_t number = 0;
  for (char c : value) {
    if (c < '0' || c > '9' || number > (maximum - uint32_t(c - '0')) / 10) {
      return false;
    }
    number = number * 10 + uint32_t(c - '0');
  }
  if (!number || number > maximum) {
    return false;
  }
  result = number;
  return true;
}
std::string summaryText(const Summary& s) {
  std::ostringstream out;
  out << "条目 " << s.entries << "  ·  文件 " << s.files << "  ·  原始数据 " << s.bytes
      << " B  ·  备份大小 " << s.archive_bytes << " B";
  return out.str();
}
NSString* byteCount(uint64_t bytes) {
  return [NSByteCountFormatter stringFromByteCount:static_cast<long long>(bytes)
                                        countStyle:NSByteCountFormatterCountStyleFile];
}
NSString* phaseName(Phase phase) {
  switch (phase) {
    case Phase::Scan:
      return @"扫描目录";
    case Phase::Pack:
      return @"打包文件";
    case Phase::Seal:
      return @"写入备份文件";
    case Phase::Authenticate:
      return @"校验备份完整性";
    case Phase::Decode:
      return @"读取备份数据";
    case Phase::Read:
      return @"处理目录与文件";
    case Phase::Metadata:
      return @"还原权限和时间";
    case Phase::CheckSource:
      return @"复查源目录变化";
    case Phase::Publish:
      return @"保存结果";
  }
  return @"处理中";
}
NSString* errorExplanation(const std::string& error) {
  if (error.find("Wrong password or damaged backup") != std::string::npos) {
    return @"密码不正确，或备份文件已损坏。请检查密码和文件来源。";
  }
  if (error.find("requires a password") != std::string::npos) {
    return @"这是一个加密备份，请填写创建备份时使用的密码。";
  }
  if (error.find("already exist") != std::string::npos) {
    return @"目标路径已经存在。请使用新的文件名或文件夹名。";
  }
  if (error.find("Source changed") != std::string::npos) {
    return @"备份期间源目录发生了变化。本次结果未保存，请稍后重试。";
  }
  if (error.find("outside") != std::string::npos) {
    return @"备份存储位置必须在源目录之外。";
  }
  if (error.find("checksum") != std::string::npos ||
      error.find("backup format") != std::string::npos ||
      error.find("valid backup") != std::string::npos) {
    return @"文件格式不正确或完整性检查未通过，无法继续。";
  }
  return @"操作未完成，请检查路径、文件权限和可用磁盘空间。";
}
NSString* displayLog(const std::string& message) {
  const std::pair<std::string, std::string> prefixes[] = {
      {"Backup complete: ", "备份完成："},
      {"Restore complete: ", "恢复完成："},
      {"Packed: ", "已归档："},
      {"Job repository: ", "本任务目录："},
      {"Retention removed: ", "已淘汰旧快照："},
      {"Job stopped; completed snapshots: ", "任务已停止，已完成快照数："},
      {"WARNING: owner/group not restored: ", "警告：无法还原属主或属组："},
      {"WARNING: xattr not restored: ", "警告：无法还原扩展属性："},
      {"WARNING: scheduled backup failed; will retry: ", "本轮备份失败，稍后重试："},
      {"WARNING: retention cleanup failed; will retry without duplicating backup: ",
       "旧快照清理失败，将重试清理，不重复创建快照："}};
  for (const auto& prefix : prefixes) {
    if (message.rfind(prefix.first, 0) == 0) {
      return toNSString(prefix.second + message.substr(prefix.first.size()));
    }
  }
  for (const auto& prefix : {std::string("Scanned "), std::string("Verification passed: ")}) {
    const std::string suffix = " entries";
    if (message.rfind(prefix, 0) == 0 && message.size() >= prefix.size() + suffix.size() &&
        message.compare(message.size() - suffix.size(), suffix.size(), suffix) == 0) {
      auto count = message.substr(prefix.size(), message.size() - prefix.size() - suffix.size());
      return toNSString((prefix == "Scanned " ? "扫描完成，共 " : "验证通过，共 ") + count +
                        " 个条目");
    }
  }
  return toNSString(message);
}
}  // namespace squirrel::ui
