// Copyright 2026 Squirrel Backup course project.
#import <Cocoa/Cocoa.h>
#include <chrono>
#include <fstream>
#include <memory>
#include <sstream>
#include "squirrel/backup.h"
using namespace squirrel;
namespace {
std::string previewDirectory;
std::string selfTestDirectory;
int previewPage = 0;
NSColor* accent() { return [NSColor colorWithSRGBRed:0.84 green:0.36 blue:0.16 alpha:1]; }
NSString* ns(const std::string& s) {
  NSString* value = [[NSString alloc] initWithBytes:s.data()
                                             length:s.size()
                                           encoding:NSUTF8StringEncoding];
  return value ? value : @"[非 UTF-8 文件名]";
}
std::string cpp(NSString* s) {
  const char* value = s.UTF8String;
  return value ? value : "";
}
NSTextField* label(NSView* parent, NSString* text, NSRect frame, CGFloat size, BOOL bold = NO) {
  NSTextField* l = [NSTextField labelWithString:text];
  l.frame = frame;
  l.font = bold ? [NSFont boldSystemFontOfSize:size] : [NSFont systemFontOfSize:size];
  l.textColor = NSColor.labelColor;
  [parent addSubview:l];
  return l;
}
NSTextField* input(NSView* parent, NSString* placeholder, NSRect frame, BOOL secure = NO) {
  NSTextField* f = secure ? [[NSSecureTextField alloc] initWithFrame:frame]
                          : [[NSTextField alloc] initWithFrame:frame];
  f.placeholderString = placeholder;
  f.font = [NSFont systemFontOfSize:13];
  f.bezelStyle = NSTextFieldRoundedBezel;
  [parent addSubview:f];
  return f;
}
NSButton* button(NSView* parent, NSString* title, NSRect frame, id target, SEL action,
                 BOOL primary = NO) {
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
bool positiveInteger(NSString* text, uint32_t maximum, uint32_t& result) {
  auto value = cpp(text);
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
std::string stats(const Summary& s) {
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
    case Phase::Scan: return @"扫描目录";
    case Phase::Pack: return @"打包文件";
    case Phase::Seal: return @"写入备份文件";
    case Phase::Authenticate: return @"校验备份完整性";
    case Phase::Decode: return @"读取备份数据";
    case Phase::Read: return @"处理目录与文件";
    case Phase::Metadata: return @"还原权限和时间";
    case Phase::CheckSource: return @"复查源目录变化";
    case Phase::Publish: return @"保存结果";
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
      {"Backup complete: ", "备份完成："}, {"Restore complete: ", "恢复完成："},
      {"Packed: ", "已归档："}, {"Job repository: ", "本任务目录："},
      {"Retention removed: ", "已淘汰旧快照："},
      {"Job stopped; completed snapshots: ", "任务已停止，已完成快照数："},
      {"WARNING: owner/group not restored: ", "警告：无法还原属主或属组："},
      {"WARNING: xattr not restored: ", "警告：无法还原扩展属性："},
      {"WARNING: scheduled backup failed; will retry: ", "本轮备份失败，稍后重试："},
      {"WARNING: retention cleanup failed; will retry without duplicating backup: ",
       "旧快照清理失败，将重试清理，不重复创建快照："}};
  for (const auto& prefix : prefixes) {
    if (message.rfind(prefix.first, 0) == 0) {
      return ns(prefix.second + message.substr(prefix.first.size()));
    }
  }
  for (const auto& prefix : {std::string("Scanned "), std::string("Verification passed: ")}) {
    const std::string suffix = " entries";
    if (message.rfind(prefix, 0) == 0 && message.size() >= prefix.size() + suffix.size() &&
        message.compare(message.size() - suffix.size(), suffix.size(), suffix) == 0) {
      auto count = message.substr(prefix.size(), message.size() - prefix.size() - suffix.size());
      return ns((prefix == "Scanned " ? "扫描完成，共 " : "验证通过，共 ") + count + " 个条目");
    }
  }
  return ns(message);
}
}  // namespace
@interface SquirrelBackgroundView : NSView
@property(nonatomic, strong) NSColor* fillColor;
@end
@implementation SquirrelBackgroundView
- (void)drawRect:(NSRect)dirtyRect {
  [NSGraphicsContext saveGraphicsState];
  NSRectClip(self.bounds);
  [self.fillColor setFill];
  NSRectFill(NSIntersectionRect(dirtyRect, self.bounds));
  [NSGraphicsContext restoreGraphicsState];
}
- (BOOL)isOpaque {
  return YES;
}
@end

@interface SquirrelController : NSObject <NSApplicationDelegate, NSWindowDelegate> {
  NSWindow* _window;
  NSView* _pages[3];
  NSButton* _nav[3];
  NSTextField *_source, *_archive, *_password, *_exclude, *_name;
  NSTextField *_readArchive, *_destination, *_readPassword;
  NSTextField *_jobSource, *_repository, *_interval, *_retention, *_status;
  NSButton *_compress, *_encrypt, *_watch, *_jobEncrypt, *_stopButton;
  NSTextField* _jobPassword;
  NSTextView* _logView;
  NSProgressIndicator* _progress;
  NSTextField* _currentPath;
  NSMutableArray<NSButton*>* _actions;
  BOOL _busy, _jobRunning, _closeWhenFinished, _quitWhenFinished;
  std::atomic<bool> _stop;
  int _testPhase;
  int _testAssertions;
  fs::path _testRoot;
  NSDate* _testStarted;
}
@end
@implementation SquirrelController
- (void)applicationDidFinishLaunching:(NSNotification*)notification {
  (void)notification;
  _stop.store(false);
  _actions = [NSMutableArray array];
  _window =
      [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 1080, 790)
                                  styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                                            NSWindowStyleMaskMiniaturizable
                                    backing:NSBackingStoreBuffered
                                      defer:NO];
  _window.title = @"松鼠备份  ·  Squirrel Backup";
  _window.delegate = self;
  _window.backgroundColor = [NSColor colorWithSRGBRed:0.97 green:0.965 blue:0.95 alpha:1];
  _window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameAqua];
  SquirrelBackgroundView* root =
      [[SquirrelBackgroundView alloc] initWithFrame:NSMakeRect(0, 0, 1080, 790)];
  root.fillColor = _window.backgroundColor;
  _window.contentView = root;
  SquirrelBackgroundView* sidebar =
      [[SquirrelBackgroundView alloc] initWithFrame:NSMakeRect(0, 0, 200, 790)];
  sidebar.fillColor = [NSColor colorWithSRGBRed:0.14 green:0.18 blue:0.20 alpha:1];
  [root addSubview:sidebar];
  NSTextField* brand = label(sidebar, @"松鼠备份", NSMakeRect(25, 710, 155, 36), 26, YES);
  brand.textColor = NSColor.whiteColor;
  NSTextField* sub = label(sidebar, @"SQUIRREL BACKUP", NSMakeRect(26, 682, 160, 22), 10);
  sub.textColor = NSColor.lightGrayColor;
  NSArray* titles = @[ @"01   创建备份", @"02   恢复与验证", @"03   自动任务" ];
  for (int i = 0; i < 3; ++i) {
    _nav[i] = button(sidebar, titles[i], NSMakeRect(16, 580 - i * 55, 168, 40), self,
                     @selector(navigate:));
    _nav[i].tag = i;
    [_nav[i] setButtonType:NSButtonTypePushOnPushOff];
  }
  NSTextField* foot = label(sidebar, @"文件备份与恢复\nmacOS\nv0.2.0",
                            NSMakeRect(25, 32, 155, 66), 11);
  foot.textColor = NSColor.lightGrayColor;
  foot.maximumNumberOfLines = 3;
  label(root, @"文件备份与恢复", NSMakeRect(235, 714, 800, 42), 28, YES);
  NSTextField* intro = label(root, @"备份保存在本机，恢复到新的文件夹。",
                             NSMakeRect(237, 682, 780, 26), 13);
  intro.textColor = NSColor.secondaryLabelColor;
  for (int i = 0; i < 3; ++i) {
    _pages[i] = [[NSView alloc] initWithFrame:NSMakeRect(235, 290, 810, 380)];
    [root addSubview:_pages[i]];
  }
  [self buildBackup];
  [self buildRestore];
  [self buildJobs];
  for (NSTextField* field in @[ _source, _archive, _readArchive, _destination,
                                 _jobSource, _repository ]) {
    field.cell.lineBreakMode = NSLineBreakByTruncatingMiddle;
    field.cell.usesSingleLineMode = YES;
    field.cell.scrollable = NO;
  }
  [self loadSettings];
  _status = label(root, @"就绪  ·  选择源目录即可开始", NSMakeRect(238, 251, 610, 25), 13, YES);
  _progress = [[NSProgressIndicator alloc] initWithFrame:NSMakeRect(858, 253, 22, 22)];
  _progress.style = NSProgressIndicatorStyleSpinning;
  _progress.displayedWhenStopped = NO;
  [root addSubview:_progress];
  _stopButton = button(root, @"取消操作", NSMakeRect(890, 247, 148, 30), self,
                       @selector(stopJob:));
  _stopButton.enabled = NO;
  _currentPath = label(root, @"", NSMakeRect(238, 225, 800, 22), 11);
  _currentPath.lineBreakMode = NSLineBreakByTruncatingMiddle;
  _currentPath.textColor = NSColor.secondaryLabelColor;
  NSScrollView* scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(238, 30, 800, 187)];
  scroll.hasVerticalScroller = YES;
  scroll.borderType = NSBezelBorder;
  _logView = [[NSTextView alloc] initWithFrame:scroll.bounds];
  _logView.editable = NO;
  _logView.font = [NSFont monospacedSystemFontOfSize:11 weight:NSFontWeightRegular];
  _logView.textContainerInset = NSMakeSize(10, 10);
  scroll.documentView = _logView;
  [root addSubview:scroll];
  [self showPage:0];
  if (!previewDirectory.empty()) {
    fs::create_directories(previewDirectory);
    for (int page = previewPage; page <= previewPage; ++page) {
      [self showPage:page];
      NSData* data = [root dataWithPDFInsideRect:root.bounds];
      NSString* output =
          ns((fs::path(previewDirectory) / ("page-" + std::to_string(page) + ".pdf")).string());
      if (![data writeToFile:output atomically:YES]) {
        std::exit(2);
      }
    }
    [NSApp terminate:nil];
    return;
  }
  if (!selfTestDirectory.empty()) {
    _testRoot = fs::absolute(selfTestDirectory);
    fs::create_directories(_testRoot / "source");
    fs::create_directories(_testRoot / "repository");
    std::ofstream(_testRoot / "source" / "中文.txt") << "GUI handler roundtrip";
    _testPhase = 0;
    _testAssertions = 0;
    _testStarted = NSDate.date;
    [NSTimer scheduledTimerWithTimeInterval:0.1
                                     target:self
                                   selector:@selector(selfTestTick:)
                                   userInfo:nil
                                    repeats:YES];
    return;
  }
  [_window center];
  [_window makeKeyAndOrderFront:nil];
  [NSApp activateIgnoringOtherApps:YES];
  [self appendLog:@"欢迎使用松鼠备份。恢复时请输入一个尚不存在的新文件夹路径，原文件不会被覆盖。"];
}
- (void)testCheck:(BOOL)condition message:(const char*)message {
  if (!condition) {
    throw Error(message);
  }
  ++_testAssertions;
}
- (void)captureEvidence:(NSString*)name page:(NSInteger)page {
  [self showPage:page];
  NSData* data = [_window.contentView dataWithPDFInsideRect:_window.contentView.bounds];
  if (![data writeToFile:ns((_testRoot / (cpp(name) + ".pdf")).string()) atomically:YES]) {
    throw Error("Could not write GUI evidence");
  }
  std::ofstream(_testRoot / "gui-events.txt") << cpp(_logView.string);
}
- (void)selfTestTick:(NSTimer*)timer {
  try {
    if ([NSDate.date timeIntervalSinceDate:_testStarted] > 30) {
      throw Error("GUI internal test timed out");
    }
    if (_busy && _testPhase != 6 && _testPhase != 10) {
      return;
    }
    switch (_testPhase) {
      case 0: {
        uint32_t parsed = 0;
        [self testCheck:positiveInteger(@"8640000", 8640000, parsed) && parsed == 8640000
                message:"Maximum interval should be accepted"];
        for (NSString* invalid in @[ @"", @"0", @"-1", @"1.5", @"1abc", @"1e3",
                                     @"8640001", @"99999999999999999999999999" ]) {
          [self testCheck:!positiveInteger(invalid, 8640000, parsed)
                  message:"Invalid integer accepted"];
        }
        [self testCheck:!_stopButton.enabled message:"Stop should be disabled while idle"];
        [self stopJob:nil];
        [self testCheck:!_stop.load() message:"Idle stop should not alter state"];
        _jobSource.stringValue = ns((_testRoot / "source").string());
        _repository.stringValue = ns((_testRoot / "repository").string());
        _interval.stringValue = @"1.5";
        [self startJob:nil];
        [self testCheck:!_busy message:"Fractional interval must not start a job"];
        _interval.stringValue = @"300";
        [self backup:nil];
        [self testCheck:!_busy message:"Empty GUI inputs should not start a task"];
        _source.stringValue = ns((_testRoot / "source").string());
        _archive.stringValue = ns((_testRoot / "backup.sqbk").string());
        _encrypt.state = NSControlStateValueOn;
        [self encryptionChanged:nil];
        [self testCheck:_password.enabled message:"Encryption switch should enable password field"];
        _password.stringValue = @"gui-test-password";
        _jobPassword.stringValue = @"job-secret-must-not-save";
        _readPassword.stringValue = @"restore-secret-must-not-save";
        NSDictionary* settings = [self settings];
        [self testCheck:settings.count == 14 message:"Only whitelisted settings may be saved"];
        for (NSString* secret in @[ _password.stringValue, _jobPassword.stringValue,
                                    _readPassword.stringValue ]) {
          [self testCheck:![settings.allValues containsObject:secret]
                  message:"Password leaked into saved settings"];
        }
        [self backup:nil];
        [self testCheck:_busy message:"Backup should set busy state"];
        [self testCheck:!_actions.firstObject.enabled
                message:"Busy state should disable backup action"];
        [self testCheck:_stopButton.enabled
                message:"One-off backup must support cancellation"];
        _testPhase = 1;
        break;
      }
      case 1:
        [self testCheck:fs::exists(_testRoot / "backup.sqbk")
                message:"GUI backup did not publish a file"];
        [self testCheck:[_readArchive.stringValue isEqualToString:_archive.stringValue]
                message:"Backup should prefill the restore archive"];
        [self captureEvidence:@"01-backup-completed" page:0];
        _readArchive.stringValue = _archive.stringValue;
        _destination.stringValue = ns((_testRoot / "restored").string());
        _readPassword.stringValue = @"wrong-password";
        [self restore:nil];
        _testPhase = 2;
        break;
      case 2:
        [self testCheck:!fs::exists(_testRoot / "restored")
                message:"Wrong password published output"];
        [self testCheck:[_status.stringValue containsString:@"未完成"]
                message:"Error was not reported in status"];
        [self testCheck:[_logView.string containsString:@"密码不正确"]
                message:"Wrong password should have a Chinese explanation"];
        [self captureEvidence:@"02-wrong-password" page:1];
        _readPassword.stringValue = @"gui-test-password";
        [self restore:nil];
        _testPhase = 3;
        break;
      case 3: {
        std::ifstream in(_testRoot / "restored" / "中文.txt");
        std::string content{std::istreambuf_iterator<char>(in), {}};
        [self testCheck:content == "GUI handler roundtrip" message:"GUI restore content mismatch"];
        [self captureEvidence:@"03-restored" page:1];
        [self list:nil];
        _testPhase = 4;
        break;
      }
      case 4:
        [self testCheck:[_logView.string containsString:@"中文.txt"]
                message:"GUI listing missing content"];
        [self verify:nil];
        _testPhase = 5;
        break;
      case 5:
        [self testCheck:[_status.stringValue isEqualToString:@"已完成"]
                message:"GUI verify did not succeed"];
        _jobSource.stringValue = _source.stringValue;
        _repository.stringValue = ns((_testRoot / "repository").string());
        _interval.stringValue = @"1";
        _retention.stringValue = @"2";
        [self startJob:nil];
        [self testCheck:_stopButton.enabled message:"Active job must enable stop"];
        _testPhase = 6;
        break;
      case 6: {
        int files = 0;
        bool third = false;
        for (const auto& entry : fs::recursive_directory_iterator(_testRoot / "repository")) {
          if (entry.path().extension() == ".sqbk") {
            ++files;
          }
          if (entry.path().filename() == "snapshot-3.sqbk") {
            third = true;
          }
        }
        if (!third) {
          return;
        }
        // Publication precedes retention by a few instructions; allow the worker to settle.
        if (files != 2) {
          return;
        }
        [self captureEvidence:@"04-retention-running" page:2];
        [self stopJob:nil];
        [self testCheck:!_stopButton.enabled message:"Pending stop must disable stop button"];
        _testPhase = 7;
        break;
      }
      case 7:
        [self testCheck:!_jobRunning && !_stopButton.enabled
                message:"Completed job must clear job state"];
        [self testCheck:_actions.firstObject.enabled message:"Actions not re-enabled after stop"];
        [self testCheck:[_logView.string containsString:@"自动任务已停止"]
                message:"Stop completion missing"];
        [self captureEvidence:@"05-job-stopped" page:2];
        _archive.stringValue = ns((_testRoot / "cancelled.sqbk").string());
        [self backup:nil];
        [self testCheck:!_source.enabled && !_password.enabled
                message:"Busy task should disable editable inputs"];
        [self testCheck:![self windowShouldClose:_window] && _closeWhenFinished && _stop.load()
                message:"Closing a busy window should request cancellation and defer closing"];
        // Check the delegate's decision without actually closing the test window.
        _closeWhenFinished = NO;
        _testPhase = 8;
        break;
      case 8:
        [self testCheck:!fs::exists(_testRoot / "cancelled.sqbk")
                message:"Cancelled GUI backup published an output"];
        [self testCheck:[_status.stringValue isEqualToString:@"已取消"]
                message:"Cancellation should be distinct from an error"];
        [self testCheck:_source.enabled && _password.enabled && !_stopButton.enabled
                message:"Inputs did not recover after cancellation"];
        for (const auto& entry : fs::directory_iterator(_testRoot)) {
          [self testCheck:entry.path().filename().string().find(".squirrel-") != 0
                  message:"Cancelled operation left temporary files"];
        }
        [self captureEvidence:@"06-cancelled" page:0];
        _watch.state = NSControlStateValueOn;
        [self watchChanged:nil];
        [self testCheck:!_interval.enabled message:"Watch mode should disable unused interval"];
        _interval.stringValue = @"unused-value";
        _repository.stringValue = ns((_testRoot / "watch-repository").string());
        fs::create_directory(_testRoot / "watch-repository");
        [self startJob:nil];
        [self testCheck:_busy && _jobRunning
                message:"Watch mode must ignore the unused periodic interval"];
        _testPhase = 10;
        break;
      case 10: {
        bool published = false;
        for (const auto& entry : fs::recursive_directory_iterator(_testRoot / "watch-repository")) {
          published |= entry.path().extension() == ".sqbk";
        }
        if (!published) {
          return;
        }
        [self testCheck:[self applicationShouldTerminate:NSApp] == NSTerminateCancel &&
                           _quitWhenFinished && _stop.load()
                message:"Quit should wait for cancellation and cleanup"];
        _quitWhenFinished = NO;
        _testPhase = 11;
        break;
      }
      case 11:
        [self testCheck:!_busy && !_jobRunning && !_interval.enabled
                message:"Stopped watch should keep its unused interval disabled"];
        std::ofstream(_testRoot / "gui-selftest.json")
            << "{\"passed\":true,\"assertions\":" << _testAssertions
            << ",\"method\":\"offscreen AppKit handlers; no system picker or mouse input\"}";
        [timer invalidate];
        [NSApp terminate:nil];
        break;
    }
  } catch (const std::exception& e) {
    std::ofstream(_testRoot / "gui-selftest-error.txt") << e.what();
    std::exit(1);
  }
}

- (void)buildBackup {
  NSView* p = _pages[0];
  label(p, @"创建备份", NSMakeRect(0, 340, 700, 30), 19, YES);
  label(p, @"源目录", NSMakeRect(0, 300, 95, 24), 13);
  _source = input(p, @"选择要备份的文件夹", NSMakeRect(100, 299, 590, 28));
  button(p, @"选择…", NSMakeRect(700, 299, 100, 28), self, @selector(chooseSource:));
  label(p, @"备份文件", NSMakeRect(0, 257, 95, 24), 13);
  _archive = input(p, @"保存为 .sqbk 文件", NSMakeRect(100, 256, 590, 28));
  button(p, @"另存为…", NSMakeRect(700, 256, 100, 28), self, @selector(chooseOutput:));
  _compress = [NSButton checkboxWithTitle:@"压缩备份文件"
                                   target:nil
                                   action:nil];
  _compress.frame = NSMakeRect(100, 214, 450, 26);
  _compress.state = NSControlStateValueOn;
  [p addSubview:_compress];
  _encrypt = [NSButton checkboxWithTitle:@"密码加密"
                                  target:self
                                  action:@selector(encryptionChanged:)];
  _encrypt.frame = NSMakeRect(100, 177, 150, 26);
  [p addSubview:_encrypt];
  _password = input(p, @"至少 8 位英文字母或数字；请妥善保存", NSMakeRect(260, 177, 430, 28), YES);
  _password.enabled = NO;
  label(p, @"排除规则", NSMakeRect(0, 134, 95, 24), 13);
  _exclude =
      input(p, @"例如 *.tmp, .DS_Store, node_modules（逗号分隔）", NSMakeRect(100, 133, 590, 28));
  _exclude.stringValue = @".DS_Store";
  label(p, @"文件名筛选", NSMakeRect(0, 91, 95, 24), 13);
  _name = input(p, @"例如 *.txt；留空包含全部文件，目录始终保留", NSMakeRect(100, 90, 590, 28));
  label(p, @"压缩后更大时保留原始数据。备份文件必须保存在源目录之外。",
        NSMakeRect(100, 57, 700, 20), 11);
  [_actions
      addObject:button(p, @"开始备份", NSMakeRect(100, 8, 160, 36), self, @selector(backup:), YES)];
}
- (void)buildRestore {
  NSView* p = _pages[1];
  label(p, @"恢复与验证", NSMakeRect(0, 340, 730, 30), 19, YES);
  label(p, @"备份文件", NSMakeRect(0, 295, 95, 24), 13);
  _readArchive = input(p, @"选择已有 .sqbk 备份", NSMakeRect(100, 294, 590, 28));
  button(p, @"打开…", NSMakeRect(700, 294, 100, 28), self, @selector(chooseArchive:));
  label(p, @"恢复到", NSMakeRect(0, 246, 95, 24), 13);
  _destination = input(p, @"新文件夹的完整路径（不能已经存在）", NSMakeRect(100, 245, 590, 28));
  button(p, @"选择位置…", NSMakeRect(700, 245, 100, 28), self, @selector(chooseRestore:));
  label(p, @"解密密码", NSMakeRect(0, 197, 95, 24), 13);
  _readPassword = input(p, @"未加密的备份请留空", NSMakeRect(100, 196, 590, 28), YES);
  NSTextField* tip = label(p,
                           @"恢复前会自动检查完整性。密码错误或文件损坏时，恢复不会继续。\n"
                           @"请选择尚不存在的新文件夹，已有文件不会被覆盖。",
                           NSMakeRect(100, 115, 690, 60), 12);
  tip.maximumNumberOfLines = 3;
  tip.textColor = NSColor.secondaryLabelColor;
  [_actions addObject:button(p, @"开始恢复", NSMakeRect(100, 45, 160, 36), self,
                             @selector(restore:), YES)];
  [_actions
      addObject:button(p, @"验证完整性", NSMakeRect(280, 45, 150, 36), self, @selector(verify:))];
  [_actions addObject:button(p, @"查看内容", NSMakeRect(450, 45, 150, 36), self, @selector(list:))];
}
- (void)buildJobs {
  NSView* p = _pages[2];
  label(p, @"自动备份", NSMakeRect(0, 340, 730, 30), 19, YES);
  label(p, @"源目录", NSMakeRect(0, 298, 95, 24), 13);
  _jobSource = input(p, @"选择自动备份的目录", NSMakeRect(100, 297, 590, 28));
  button(p, @"选择…", NSMakeRect(700, 297, 100, 28), self, @selector(chooseJobSource:));
  label(p, @"存储目录", NSMakeRect(0, 256, 95, 24), 13);
  _repository = input(p, @"已有的备份存储目录；必须在源目录之外", NSMakeRect(100, 255, 590, 28));
  button(p, @"选择…", NSMakeRect(700, 255, 100, 28), self, @selector(chooseRepository:));
  label(p, @"间隔（秒）", NSMakeRect(0, 214, 95, 24), 13);
  _interval = input(p, @"300", NSMakeRect(100, 213, 100, 28));
  _interval.stringValue = @"300";
  label(p, @"保留份数", NSMakeRect(240, 214, 95, 24), 13);
  _retention = input(p, @"5", NSMakeRect(335, 213, 100, 28));
  _retention.stringValue = @"5";
  _watch = [NSButton checkboxWithTitle:@"目录变化后备份（每 2 秒检查，稳定后执行）"
                                target:self
                                action:@selector(watchChanged:)];
  _watch.frame = NSMakeRect(100, 172, 600, 26);
  [p addSubview:_watch];
  _jobEncrypt = [NSButton checkboxWithTitle:@"密码加密"
                                     target:self
                                     action:@selector(encryptionChanged:)];
  _jobEncrypt.frame = NSMakeRect(100, 131, 150, 26);
  [p addSubview:_jobEncrypt];
  _jobPassword =
      input(p, @"至少 8 位英文字母或数字；退出后不保存", NSMakeRect(260, 130, 430, 28), YES);
  _jobPassword.enabled = NO;
  label(p, @"每次启动使用独立任务目录，淘汰只清理本任务生成的备份。", NSMakeRect(100, 92, 700, 20),
        11);
  label(p, @"任务需要保持应用运行；电脑休眠时暂停。源目录持续变化时会延迟备份。",
        NSMakeRect(100, 67, 700, 20), 11);
  [_actions addObject:button(p, @"启动任务", NSMakeRect(100, 8, 160, 36), self,
                             @selector(startJob:), YES)];
}
// Only these explicit non-sensitive fields are persisted. Passwords never enter defaults.
- (NSDictionary*)settings {
  return @{
    @"source" : _source.stringValue, @"archive" : _archive.stringValue,
    @"exclude" : _exclude.stringValue, @"name" : _name.stringValue,
    @"readArchive" : _readArchive.stringValue, @"destination" : _destination.stringValue,
    @"jobSource" : _jobSource.stringValue, @"repository" : _repository.stringValue,
    @"interval" : _interval.stringValue, @"retention" : _retention.stringValue,
    @"compress" : @(_compress.state == NSControlStateValueOn),
    @"encrypt" : @(_encrypt.state == NSControlStateValueOn),
    @"watch" : @(_watch.state == NSControlStateValueOn),
    @"jobEncrypt" : @(_jobEncrypt.state == NSControlStateValueOn)
  };
}
- (void)saveSettings {
  if (!previewDirectory.empty() || !selfTestDirectory.empty()) {
    return;
  }
  [NSUserDefaults.standardUserDefaults setObject:[self settings]
                                          forKey:@"SquirrelBackup.FormSettings.v1"];
}
- (void)loadSettings {
  if (!previewDirectory.empty() || !selfTestDirectory.empty()) {
    return;
  }
  NSDictionary* settings = [NSUserDefaults.standardUserDefaults
      dictionaryForKey:@"SquirrelBackup.FormSettings.v1"];
  NSDictionary* fields = @{
    @"source" : _source, @"archive" : _archive, @"exclude" : _exclude, @"name" : _name,
    @"readArchive" : _readArchive, @"destination" : _destination,
    @"jobSource" : _jobSource, @"repository" : _repository,
    @"interval" : _interval, @"retention" : _retention
  };
  for (NSString* key in fields) {
    if ([settings[key] isKindOfClass:NSString.class]) {
      ((NSTextField*)fields[key]).stringValue = settings[key];
    }
  }
  NSDictionary* switches = @{
    @"compress" : _compress, @"encrypt" : _encrypt,
    @"watch" : _watch, @"jobEncrypt" : _jobEncrypt
  };
  for (NSString* key in switches) {
    if ([settings[key] isKindOfClass:NSNumber.class]) {
      ((NSButton*)switches[key]).state = [settings[key] boolValue]
                                          ? NSControlStateValueOn : NSControlStateValueOff;
    }
  }
  [self encryptionChanged:nil];
  [self watchChanged:nil];
}
- (void)appendLog:(NSString*)line {
  NSString* stamp = [NSDateFormatter localizedStringFromDate:NSDate.date
                                                   dateStyle:NSDateFormatterNoStyle
                                                   timeStyle:NSDateFormatterMediumStyle];
  NSString* text = [NSString stringWithFormat:@"[%@] %@\n", stamp, line];
  [_logView.textStorage
      appendAttributedString:[[NSAttributedString alloc]
                                 initWithString:text
                                     attributes:@{
                                       NSFontAttributeName :
                                           [NSFont monospacedSystemFontOfSize:11
                                                                       weight:NSFontWeightRegular]
                                     }]];
  if (_logView.string.length > 180000) {
    [_logView.textStorage deleteCharactersInRange:NSMakeRange(0, 90000)];
  }
  [_logView scrollRangeToVisible:NSMakeRange(_logView.string.length, 0)];
}
- (void)showPage:(NSInteger)index {
  if (_status && !_busy && [_status.stringValue hasPrefix:@"就绪"]) {
    NSArray* hints = @[
      @"就绪 · 选择源目录即可开始", @"就绪 · 选择备份文件进行验证或恢复",
      @"就绪 · 设置目录、周期和保留份数"
    ];
    _status.stringValue = hints[index];
  }
  for (int i = 0; i < 3; ++i) {
    _pages[i].hidden = i != index;
    _nav[i].state = i == index ? NSControlStateValueOn : NSControlStateValueOff;
  }
}
- (void)navigate:(NSButton*)sender {
  [self showPage:sender.tag];
}
- (void)encryptionChanged:(id)sender {
  (void)sender;
  _password.enabled = !_busy && _encrypt.state == NSControlStateValueOn;
  _jobPassword.enabled = !_busy && _jobEncrypt.state == NSControlStateValueOn;
}
- (void)watchChanged:(id)sender {
  (void)sender;
  _interval.enabled = !_busy && _watch.state != NSControlStateValueOn;
}
- (NSString*)chooseDirectory {
  NSOpenPanel* panel = [NSOpenPanel openPanel];
  panel.canChooseFiles = NO;
  panel.canChooseDirectories = YES;
  panel.allowsMultipleSelection = NO;
  return [panel runModal] == NSModalResponseOK ? panel.URL.path : nil;
}
- (void)chooseSource:(id)sender {
  (void)sender;
  NSString* p = [self chooseDirectory];
  if (p) {
    _source.stringValue = p;
  }
}
- (void)chooseJobSource:(id)sender {
  (void)sender;
  NSString* p = [self chooseDirectory];
  if (p) {
    _jobSource.stringValue = p;
  }
}
- (void)chooseRepository:(id)sender {
  (void)sender;
  NSString* p = [self chooseDirectory];
  if (p) {
    _repository.stringValue = p;
  }
}
- (void)chooseOutput:(id)sender {
  (void)sender;
  NSSavePanel* panel = [NSSavePanel savePanel];
  panel.nameFieldStringValue = @"我的备份.sqbk";
  if ([panel runModal] == NSModalResponseOK) {
    _archive.stringValue = panel.URL.path;
  }
}
- (void)chooseArchive:(id)sender {
  (void)sender;
  NSOpenPanel* panel = [NSOpenPanel openPanel];
  panel.canChooseDirectories = NO;
  panel.allowsMultipleSelection = NO;
  if ([panel runModal] == NSModalResponseOK) {
    _readArchive.stringValue = panel.URL.path;
  }
}
- (void)chooseRestore:(id)sender {
  (void)sender;
  NSSavePanel* panel = [NSSavePanel savePanel];
  panel.nameFieldStringValue = @"恢复副本";
  panel.title = @"指定尚不存在的恢复文件夹";
  if ([panel runModal] == NSModalResponseOK) {
    _destination.stringValue = panel.URL.path;
  }
}
- (Log)logger {
  return [self](const std::string& text) {
    NSString* line = displayLog(text);
    dispatch_async(dispatch_get_main_queue(), ^{
      [self appendLog:line];
    });
  };
}
- (Operation)operation {
  struct State {
    std::chrono::steady_clock::time_point last{};
    Phase phase = Phase::Scan;
  };
  auto state = std::make_shared<State>();
  return Operation{&_stop, [self, state](const ProgressInfo& info) {
    auto now = std::chrono::steady_clock::now();
    if (state->phase == info.phase && now - state->last < std::chrono::milliseconds(150)) {
      return;
    }
    state->last = now;
    state->phase = info.phase;
    NSString* title = phaseName(info.phase);
    if (info.total) {
      if (info.phase == Phase::Metadata) {
        title = [NSString stringWithFormat:@"%@ · %llu / %llu 项", title,
                                            info.completed, info.total];
      } else {
        title = [NSString stringWithFormat:@"%@ · %@ / %@", title,
                                            byteCount(info.completed), byteCount(info.total)];
      }
    } else if (info.phase == Phase::Scan && info.completed) {
      title = [NSString stringWithFormat:@"%@ · 已发现 %llu 项", title, info.completed];
    }
    NSString* path = ns(info.path);
    dispatch_async(dispatch_get_main_queue(), ^{
      if (self->_busy && !self->_stop.load()) {
        self->_status.stringValue = title;
        self->_currentPath.stringValue = path;
      }
    });
  }};
}
- (void)setInputsEnabled:(BOOL)enabled {
  for (NSView* page : _pages) {
    for (NSView* view in page.subviews) {
      if ([view isKindOfClass:NSButton.class] ||
          ([view isKindOfClass:NSTextField.class] && ((NSTextField*)view).editable)) {
        ((NSControl*)view).enabled = enabled;
      }
    }
  }
  [self encryptionChanged:nil];
  [self watchChanged:nil];
}
- (void)perform:(NSString*)title work:(std::function<std::string()>)work {
  if (_busy) {
    return;
  }
  _busy = YES;
  [self saveSettings];
  _stopButton.enabled = YES;
  _stopButton.title = _jobRunning ? @"停止任务" : @"取消操作";
  _stop.store(false);
  _status.stringValue = title;
  _currentPath.stringValue = @"";
  [_progress startAnimation:nil];
  [self setInputsEnabled:NO];
  BOOL wasJob = _jobRunning;
  [self appendLog:title];
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
    NSString* result;
    BOOL success = YES;
    BOOL cancelled = NO;
    try {
      result = ns(work());
    } catch (const Cancelled&) {
      cancelled = YES;
      result = @"操作已取消，未完成的临时文件已清理。";
    } catch (const std::exception& e) {
      success = NO;
      result = [NSString stringWithFormat:@"%@\n详细原因：%@", errorExplanation(e.what()), ns(e.what())];
    }
    dispatch_async(dispatch_get_main_queue(), ^{
      self->_busy = NO;
      self->_jobRunning = NO;
      self->_stopButton.enabled = NO;
      [self->_progress stopAnimation:nil];
      [self setInputsEnabled:YES];
      self->_currentPath.stringValue = @"";
      self->_status.stringValue = cancelled ? @"已取消" : !success
          ? @"未完成 · 请查看下方原因" : wasJob ? @"已停止" : @"已完成";
      [self appendLog:result];
      if (self->_quitWhenFinished) {
        [NSApp terminate:nil];
      } else if (self->_closeWhenFinished) {
        [self->_window performClose:nil];
      }
    });
  });
}
- (void)backup:(id)sender {
  (void)sender;
  std::string source = cpp(_source.stringValue), archive = cpp(_archive.stringValue);
  if (source.empty() || archive.empty()) {
    [self appendLog:@"请先填写源目录和备份文件路径。"];
    return;
  }
  BackupOptions options;
  options.compress = _compress.state == NSControlStateValueOn;
  if (_encrypt.state == NSControlStateValueOn) {
    options.password = cpp(_password.stringValue);
    if (options.password.size() < 8) {
      [self appendLog:@"加密密码至少需要 8 字节。"];
      return;
    }
  }
  for (NSString* raw in [_exclude.stringValue componentsSeparatedByString:@","]) {
    NSString* s = [raw stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
    if (s.length) {
      options.filter.excludes.push_back(cpp(s));
    }
  }
  options.filter.name_pattern = cpp(_name.stringValue);
  Log log = [self logger];
  Operation operation = [self operation];
  [self perform:@"正在备份…"
           work:[=] {
             auto summary = BackupService{}.backup(source, archive, options, log, operation);
             dispatch_async(dispatch_get_main_queue(), ^{
               self->_readArchive.stringValue = ns(archive);
             });
             return stats(summary);
           }];
}
- (void)readAction:(int)mode {
  std::string archive = cpp(_readArchive.stringValue), dest = cpp(_destination.stringValue),
              password = cpp(_readPassword.stringValue);
  if (archive.empty() || (mode == 0 && dest.empty())) {
    [self appendLog:@"请先填写备份文件路径；恢复操作还需填写新文件夹路径。"];
    return;
  }
  Log log = [self logger];
  Operation operation = [self operation];
  [self perform:mode == 0 ? @"正在验证并恢复…" : @"正在验证备份…"
           work:[=] {
             Summary result = mode == 0
                                  ? BackupService{}.restore(archive, dest, password, log, operation)
                                  : BackupService{}.inspect(archive, password, log, mode == 2,
                                                             operation);
             if (mode == 2) {
               size_t shown = 0;
               for (const auto& e : result.items) {
                 if (++shown > 300) {
                   log("更多条目请使用 CLI list 查看。");
                   break;
                 }
                 log(typeName(e.type) + "  " + (e.path.empty() ? "." : e.path));
               }
             }
             return stats(result);
           }];
}
- (void)restore:(id)sender {
  (void)sender;
  [self readAction:0];
}
- (void)verify:(id)sender {
  (void)sender;
  [self readAction:1];
}
- (void)list:(id)sender {
  (void)sender;
  [self readAction:2];
}
- (void)startJob:(id)sender {
  (void)sender;
  if (_busy) {
    return;
  }
  auto source = cpp(_jobSource.stringValue), repo = cpp(_repository.stringValue);
  uint32_t interval = 0, keep = 0;
  bool watch = _watch.state == NSControlStateValueOn;
  if (source.empty() || repo.empty() ||
      (!watch && !positiveInteger(_interval.stringValue, 8640000, interval)) ||
      !positiveInteger(_retention.stringValue, 10000, keep)) {
    [self appendLog:@"请检查目录；间隔须为 1–8640000 的整数，保留份数须为 1–10000 的整数。"];
    return;
  }
  BackupOptions options;
  if (_jobEncrypt.state == NSControlStateValueOn) {
    options.password = cpp(_jobPassword.stringValue);
    if (options.password.size() < 8) {
      [self appendLog:@"加密密码至少需要 8 字节。"];
      return;
    }
  }
  ScheduleOptions schedule;
  schedule.interval_seconds = watch ? 300 : interval;
  schedule.keep = keep;
  schedule.watch = watch;
  Log log = [self logger];
  Operation operation = [self operation];
  _jobRunning = YES;
  [self perform:@"自动任务运行中 · 可点击停止任务"
           work:[=] {
             Scheduler::run(source, repo, options, schedule, self->_stop, log, operation.progress);
             return std::string("自动任务已停止。备份文件已保留。");
           }];
}
- (void)stopJob:(id)sender {
  (void)sender;
  if (!_busy || _stop.exchange(true)) {
    return;
  }
  _stopButton.enabled = NO;
  _status.stringValue = @"正在取消 · 清理临时文件";
  [self appendLog:@"已请求取消。未完成的结果会清理，已经完成的备份会保留。"];
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication*)sender {
  (void)sender;
  return YES;
}
- (BOOL)windowShouldClose:(NSWindow*)sender {
  (void)sender;
  [self saveSettings];
  if (_busy) {
    _closeWhenFinished = YES;
    [self stopJob:nil];
    _status.stringValue = @"正在取消，清理完成后关闭窗口";
    [self appendLog:@"正在结束当前操作，完成清理后自动关闭。"];
    return NO;
  }
  return YES;
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication*)sender {
  (void)sender;
  [self saveSettings];
  if (_busy) {
    _quitWhenFinished = YES;
    [self stopJob:nil];
    _status.stringValue = @"正在取消，清理完成后退出";
    [self appendLog:@"正在结束当前操作，完成清理后自动退出。"];
    return NSTerminateCancel;
  }
  return NSTerminateNow;
}
@end
int main(int argc, const char* argv[]) {
  if (argc >= 3 && std::string(argv[1]) == "--render-preview") {
    previewDirectory = argv[2];
    if (argc == 4) {
      previewPage = std::stoi(argv[3]);
    }
    if (previewPage < 0 || previewPage > 2) {
      return 1;
    }
  }
  if (argc == 3 && std::string(argv[1]) == "--self-test") {
    selfTestDirectory = argv[2];
  }
  @autoreleasepool {
    NSApplication* app = [NSApplication sharedApplication];
    [app setActivationPolicy:previewDirectory.empty() && selfTestDirectory.empty()
                                 ? NSApplicationActivationPolicyRegular
                                 : NSApplicationActivationPolicyProhibited];
    NSMenu* bar = [[NSMenu alloc] init];
    NSMenuItem* item = [[NSMenuItem alloc] init];
    [bar addItem:item];
    NSMenu* menu = [[NSMenu alloc] initWithTitle:@"松鼠备份"];
    [menu addItemWithTitle:@"退出松鼠备份" action:@selector(terminate:) keyEquivalent:@"q"];
    item.submenu = menu;
    NSMenuItem* editItem = [[NSMenuItem alloc] init];
    [bar addItem:editItem];
    NSMenu* edit = [[NSMenu alloc] initWithTitle:@"编辑"];
    [edit addItemWithTitle:@"剪切" action:@selector(cut:) keyEquivalent:@"x"];
    [edit addItemWithTitle:@"复制" action:@selector(copy:) keyEquivalent:@"c"];
    [edit addItemWithTitle:@"粘贴" action:@selector(paste:) keyEquivalent:@"v"];
    [edit addItemWithTitle:@"全选" action:@selector(selectAll:) keyEquivalent:@"a"];
    editItem.submenu = edit;
    app.mainMenu = bar;
    SquirrelController* delegate = [[SquirrelController alloc] init];
    app.delegate = delegate;
    [app run];
  }
  return 0;
}
