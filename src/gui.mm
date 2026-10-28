// Copyright 2026 Squirrel Backup course project.
#import <Cocoa/Cocoa.h>
#include <chrono>
#include <sstream>
#include "squirrel/backup.h"
using namespace squirrel;
namespace {
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
std::string stats(const Summary& s) {
  std::ostringstream out;
  out << "条目 " << s.entries << "  ·  文件 " << s.files << "  ·  原始数据 " << s.bytes
      << " B  ·  备份大小 " << s.archive_bytes << " B";
  return out.str();
}
}  // namespace
@interface SquirrelController : NSObject <NSApplicationDelegate, NSWindowDelegate> {
  NSWindow* _window;
  NSView* _pages[3];
  NSButton* _nav[3];
  NSTextField *_source, *_archive, *_password, *_exclude, *_name;
  NSTextField *_readArchive, *_destination, *_readPassword;
  NSTextField *_jobSource, *_repository, *_interval, *_retention, *_status;
  NSButton *_compress, *_encrypt, *_watch, *_jobEncrypt;
  NSTextField* _jobPassword;
  NSTextView* _logView;
  NSProgressIndicator* _progress;
  NSMutableArray<NSButton*>* _actions;
  BOOL _busy;
  std::atomic<bool> _stop;
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
  NSView* root = _window.contentView;
  NSView* sidebar = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 200, 790)];
  sidebar.wantsLayer = YES;
  sidebar.layer.backgroundColor =
      [NSColor colorWithSRGBRed:0.14 green:0.18 blue:0.20 alpha:1].CGColor;
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
  }
  NSTextField* foot = label(sidebar, @"本机存储 · 自主掌控\nmacOS 原生课程设计\nv0.1.0 初版",
                            NSMakeRect(25, 32, 155, 66), 11);
  foot.textColor = NSColor.lightGrayColor;
  foot.maximumNumberOfLines = 3;
  label(root, @"把重要的文件，好好保存。", NSMakeRect(235, 714, 800, 42), 28, YES);
  NSTextField* intro = label(root, @"目录树备份 / 无损压缩 / 密码保护 / 安全还原",
                             NSMakeRect(237, 682, 780, 26), 13);
  intro.textColor = NSColor.secondaryLabelColor;
  for (int i = 0; i < 3; ++i) {
    _pages[i] = [[NSView alloc] initWithFrame:NSMakeRect(235, 290, 810, 380)];
    [root addSubview:_pages[i]];
  }
  [self buildBackup];
  [self buildRestore];
  [self buildJobs];
  _status = label(root, @"就绪  ·  选择源目录即可开始", NSMakeRect(238, 251, 750, 25), 13, YES);
  _progress = [[NSProgressIndicator alloc] initWithFrame:NSMakeRect(1010, 253, 22, 22)];
  _progress.style = NSProgressIndicatorStyleSpinning;
  _progress.displayedWhenStopped = NO;
  [root addSubview:_progress];
  NSScrollView* scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(238, 30, 800, 208)];
  scroll.hasVerticalScroller = YES;
  scroll.borderType = NSBezelBorder;
  _logView = [[NSTextView alloc] initWithFrame:scroll.bounds];
  _logView.editable = NO;
  _logView.font = [NSFont monospacedSystemFontOfSize:11 weight:NSFontWeightRegular];
  _logView.textContainerInset = NSMakeSize(10, 10);
  scroll.documentView = _logView;
  [root addSubview:scroll];
  [self showPage:0];
  [_window center];
  [_window makeKeyAndOrderFront:nil];
  [NSApp activateIgnoringOtherApps:YES];
  [self appendLog:@"欢迎使用松鼠备份。恢复时请输入一个尚不存在的新文件夹路径，原文件不会被覆盖。"];
}
- (void)buildBackup {
  NSView* p = _pages[0];
  label(p, @"创建一个新的备份", NSMakeRect(0, 340, 700, 30), 19, YES);
  label(p, @"源目录", NSMakeRect(0, 300, 95, 24), 13);
  _source = input(p, @"选择需要保护的文件夹", NSMakeRect(100, 299, 590, 28));
  button(p, @"选择…", NSMakeRect(700, 299, 100, 28), self, @selector(chooseSource:));
  label(p, @"备份文件", NSMakeRect(0, 257, 95, 24), 13);
  _archive = input(p, @"保存为 .sqbk 文件", NSMakeRect(100, 256, 590, 28));
  button(p, @"另存为…", NSMakeRect(700, 256, 100, 28), self, @selector(chooseOutput:));
  _compress = [NSButton checkboxWithTitle:@"Huffman 无损压缩（自动回退原始块）"
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
  _password = input(p, @"密码至少 8 字节，请自行妥善保存", NSMakeRect(260, 177, 430, 28), YES);
  _password.enabled = NO;
  label(p, @"排除规则", NSMakeRect(0, 134, 95, 24), 13);
  _exclude =
      input(p, @"例如 *.tmp, .DS_Store, node_modules（逗号分隔）", NSMakeRect(100, 133, 590, 28));
  _exclude.stringValue = @".DS_Store";
  label(p, @"文件名筛选", NSMakeRect(0, 91, 95, 24), 13);
  _name = input(p, @"例如 *.txt；留空包含全部文件，目录始终保留", NSMakeRect(100, 90, 590, 28));
  label(p, @"支持软硬链接、FIFO、权限、纳秒时间与扩展属性。更多筛选条件见 CLI。",
        NSMakeRect(100, 57, 700, 20), 11);
  [_actions
      addObject:button(p, @"开始备份", NSMakeRect(100, 8, 160, 36), self, @selector(backup:), YES)];
}
- (void)buildRestore {
  NSView* p = _pages[1];
  label(p, @"恢复之前，先确认完整性", NSMakeRect(0, 340, 730, 30), 19, YES);
  label(p, @"备份文件", NSMakeRect(0, 295, 95, 24), 13);
  _readArchive = input(p, @"选择已有 .sqbk 备份", NSMakeRect(100, 294, 590, 28));
  button(p, @"打开…", NSMakeRect(700, 294, 100, 28), self, @selector(chooseArchive:));
  label(p, @"恢复到", NSMakeRect(0, 246, 95, 24), 13);
  _destination = input(p, @"新文件夹的完整路径（不能已经存在）", NSMakeRect(100, 245, 590, 28));
  button(p, @"选择位置…", NSMakeRect(700, 245, 100, 28), self, @selector(chooseRestore:));
  label(p, @"解密密码", NSMakeRect(0, 197, 95, 24), 13);
  _readPassword = input(p, @"未加密的备份请留空", NSMakeRect(100, 196, 590, 28), YES);
  NSTextField* tip = label(p,
                           @"先验证，再解包。备份损坏、密码错误或路径不安全时会中止。\n恢复结果先写"
                           @"入私有暂存目录，成功后一次性发布到新文件夹。",
                           NSMakeRect(100, 115, 690, 60), 12);
  tip.maximumNumberOfLines = 3;
  tip.textColor = NSColor.secondaryLabelColor;
  [_actions addObject:button(p, @"安全恢复", NSMakeRect(100, 45, 160, 36), self,
                             @selector(restore:), YES)];
  [_actions
      addObject:button(p, @"验证完整性", NSMakeRect(280, 45, 150, 36), self, @selector(verify:))];
  [_actions addObject:button(p, @"查看内容", NSMakeRect(450, 45, 150, 36), self, @selector(list:))];
}
- (void)buildJobs {
  NSView* p = _pages[2];
  label(p, @"让备份成为日常习惯", NSMakeRect(0, 340, 730, 30), 19, YES);
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
  _watch = [NSButton checkboxWithTitle:@"实时模式（每 2 秒检查，稳定后备份）"
                                target:nil
                                action:nil];
  _watch.frame = NSMakeRect(100, 172, 600, 26);
  [p addSubview:_watch];
  _jobEncrypt = [NSButton checkboxWithTitle:@"密码加密"
                                     target:self
                                     action:@selector(encryptionChanged:)];
  _jobEncrypt.frame = NSMakeRect(100, 131, 150, 26);
  [p addSubview:_jobEncrypt];
  _jobPassword =
      input(p, @"至少 8 字节；仅在本次运行内存中使用", NSMakeRect(260, 130, 430, 28), YES);
  _jobPassword.enabled = NO;
  label(p, @"每次启动使用独立任务目录，淘汰只清理本任务生成的备份。", NSMakeRect(100, 92, 700, 20),
        11);
  label(p, @"任务需要保持应用运行；电脑休眠时暂停。源目录持续变化时会延迟备份。",
        NSMakeRect(100, 67, 700, 20), 11);
  [_actions addObject:button(p, @"启动任务", NSMakeRect(100, 8, 160, 36), self,
                             @selector(startJob:), YES)];
  button(p, @"停止任务", NSMakeRect(280, 8, 150, 36), self, @selector(stopJob:));
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
  _password.enabled = _encrypt.state == NSControlStateValueOn;
  _jobPassword.enabled = _jobEncrypt.state == NSControlStateValueOn;
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
    NSString* line = ns(text);
    dispatch_async(dispatch_get_main_queue(), ^{
      [self appendLog:line];
    });
  };
}
- (void)perform:(NSString*)title work:(std::function<std::string()>)work {
  if (_busy) {
    return;
  }
  _busy = YES;
  _stop.store(false);
  _status.stringValue = title;
  [_progress startAnimation:nil];
  for (NSButton* b in _actions) {
    b.enabled = NO;
  }
  [self appendLog:title];
  dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
    NSString* result;
    BOOL success = YES;
    try {
      result = ns(work());
    } catch (const std::exception& e) {
      success = NO;
      result = [@"操作失败：" stringByAppendingString:ns(e.what())];
    }
    dispatch_async(dispatch_get_main_queue(), ^{
      self->_busy = NO;
      [self->_progress stopAnimation:nil];
      for (NSButton* b in self->_actions) {
        b.enabled = YES;
      }
      self->_status.stringValue = success ? @"已完成" : @"未完成 · 请查看下方原因";
      [self appendLog:result];
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
  [self perform:@"正在备份…"
           work:[=] { return stats(BackupService{}.backup(source, archive, options, log)); }];
}
- (void)readAction:(int)mode {
  std::string archive = cpp(_readArchive.stringValue), dest = cpp(_destination.stringValue),
              password = cpp(_readPassword.stringValue);
  if (archive.empty() || (mode == 0 && dest.empty())) {
    [self appendLog:@"请先填写备份文件路径；恢复操作还需填写新文件夹路径。"];
    return;
  }
  Log log = [self logger];
  [self perform:mode == 0 ? @"正在验证并恢复…" : @"正在验证备份…"
           work:[=] {
             Summary result = mode == 0
                                  ? BackupService{}.restore(archive, dest, password, log)
                                  : BackupService{}.inspect(archive, password, log, mode == 2);
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
  auto source = cpp(_jobSource.stringValue), repo = cpp(_repository.stringValue);
  NSInteger interval = _interval.integerValue, keep = _retention.integerValue;
  if (source.empty() || repo.empty() || interval < 1 || interval > 8640000 || keep < 1 ||
      keep > 10000) {
    [self appendLog:@"请检查目录、间隔（1–8640000 秒）和保留份数（1–10000）。"];
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
  schedule.interval_seconds = interval;
  schedule.keep = keep;
  schedule.watch = _watch.state == NSControlStateValueOn;
  Log log = [self logger];
  [self perform:@"自动任务运行中 · 可点击停止任务"
           work:[=] {
             Scheduler::run(source, repo, options, schedule, self->_stop, log);
             return std::string("自动任务已停止。备份文件已保留。");
           }];
}
- (void)stopJob:(id)sender {
  (void)sender;
  _stop.store(true);
  [self appendLog:@"已请求停止；当前正在写入的快照将先完成。"];
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication*)sender {
  (void)sender;
  return YES;
}
- (BOOL)windowShouldClose:(NSWindow*)sender {
  (void)sender;
  if (_busy) {
    [self stopJob:nil];
    [self appendLog:@"请等待当前操作结束后再关闭窗口。"];
    return NO;
  }
  return YES;
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication*)sender {
  (void)sender;
  if (_busy) {
    [self stopJob:nil];
    [self appendLog:@"请等待操作完成后再退出。"];
    return NSTerminateCancel;
  }
  return NSTerminateNow;
}
@end
int main(int argc, const char* argv[]) {
  (void)argc;
  (void)argv;
  @autoreleasepool {
    NSApplication* app = [NSApplication sharedApplication];
    [app setActivationPolicy:NSApplicationActivationPolicyRegular];
    NSMenu* bar = [[NSMenu alloc] init];
    NSMenuItem* item = [[NSMenuItem alloc] init];
    [bar addItem:item];
    NSMenu* menu = [[NSMenu alloc] initWithTitle:@"松鼠备份"];
    [menu addItemWithTitle:@"退出松鼠备份" action:@selector(terminate:) keyEquivalent:@"q"];
    item.submenu = menu;
    app.mainMenu = bar;
    SquirrelController* delegate = [[SquirrelController alloc] init];
    app.delegate = delegate;
    [app run];
  }
  return 0;
}
