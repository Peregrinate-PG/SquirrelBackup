// Copyright 2026 Squirrel Backup course project.
#include "gui_controller.h"
#include "gui_support.h"

using namespace squirrel;
using namespace squirrel::ui;

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

@implementation SquirrelController (Layout)
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
  NSTextField* brand = makeLabel(sidebar, @"松鼠备份", NSMakeRect(25, 710, 155, 36), 26, YES);
  brand.textColor = NSColor.whiteColor;
  NSTextField* sub = makeLabel(sidebar, @"SQUIRREL BACKUP", NSMakeRect(26, 682, 160, 22), 10);
  sub.textColor = NSColor.lightGrayColor;
  NSArray* titles = @[ @"01   创建备份", @"02   恢复与验证", @"03   自动任务" ];
  for (int i = 0; i < 3; ++i) {
    _nav[i] = makeButton(sidebar, titles[i], NSMakeRect(16, 580 - i * 55, 168, 40), self,
                         @selector(navigate:));
    _nav[i].tag = i;
    [_nav[i] setButtonType:NSButtonTypePushOnPushOff];
  }
  NSTextField* foot =
      makeLabel(sidebar, @"文件备份与恢复\nmacOS\nv0.2.0", NSMakeRect(25, 32, 155, 66), 11);
  foot.textColor = NSColor.lightGrayColor;
  foot.maximumNumberOfLines = 3;
  makeLabel(root, @"文件备份与恢复", NSMakeRect(235, 714, 800, 42), 28, YES);
  NSTextField* intro =
      makeLabel(root, @"备份保存在本机，恢复到新的文件夹。", NSMakeRect(237, 682, 780, 26), 13);
  intro.textColor = NSColor.secondaryLabelColor;
  for (int i = 0; i < 3; ++i) {
    _pages[i] = [[NSView alloc] initWithFrame:NSMakeRect(235, 290, 810, 380)];
    [root addSubview:_pages[i]];
  }
  [self buildBackup];
  [self buildRestore];
  [self buildJobs];
  for (NSTextField* field in
       @[ _source, _archive, _readArchive, _destination, _jobSource, _repository ]) {
    field.cell.lineBreakMode = NSLineBreakByTruncatingMiddle;
    field.cell.usesSingleLineMode = YES;
    field.cell.scrollable = NO;
  }
  [self loadSettings];
  _status = makeLabel(root, @"就绪  ·  选择源目录即可开始", NSMakeRect(238, 251, 610, 25), 13, YES);
  _progress = [[NSProgressIndicator alloc] initWithFrame:NSMakeRect(858, 253, 22, 22)];
  _progress.style = NSProgressIndicatorStyleSpinning;
  _progress.displayedWhenStopped = NO;
  [root addSubview:_progress];
  _stopButton =
      makeButton(root, @"取消操作", NSMakeRect(890, 247, 148, 30), self, @selector(stopJob:));
  _stopButton.enabled = NO;
  _currentPath = makeLabel(root, @"", NSMakeRect(238, 225, 800, 22), 11);
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
      NSString* output = toNSString(
          (fs::path(previewDirectory) / ("page-" + std::to_string(page) + ".pdf")).string());
      if (![data writeToFile:output atomically:YES]) {
        std::exit(2);
      }
    }
    [NSApp terminate:nil];
    return;
  }
  if (!selfTestDirectory.empty()) {
    [self startSelfTest];
    return;
  }
  [_window center];
  [_window makeKeyAndOrderFront:nil];
  [NSApp activateIgnoringOtherApps:YES];
  [self appendLog:@"欢迎使用松鼠备份。恢复时请输入一个尚不存在的新文件夹路径，原文件不会被覆盖。"];
}
- (void)buildBackup {
  NSView* p = _pages[0];
  makeLabel(p, @"创建备份", NSMakeRect(0, 340, 700, 30), 19, YES);
  makeLabel(p, @"源目录", NSMakeRect(0, 300, 95, 24), 13);
  _source = makeInput(p, @"选择要备份的文件夹", NSMakeRect(100, 299, 590, 28));
  makeButton(p, @"选择…", NSMakeRect(700, 299, 100, 28), self, @selector(chooseSource:));
  makeLabel(p, @"备份文件", NSMakeRect(0, 257, 95, 24), 13);
  _archive = makeInput(p, @"保存为 .sqbk 文件", NSMakeRect(100, 256, 590, 28));
  makeButton(p, @"另存为…", NSMakeRect(700, 256, 100, 28), self, @selector(chooseOutput:));
  _compress = [NSButton checkboxWithTitle:@"压缩备份文件" target:nil action:nil];
  _compress.frame = NSMakeRect(100, 214, 450, 26);
  _compress.state = NSControlStateValueOn;
  [p addSubview:_compress];
  _encrypt = [NSButton checkboxWithTitle:@"密码加密"
                                  target:self
                                  action:@selector(encryptionChanged:)];
  _encrypt.frame = NSMakeRect(100, 177, 150, 26);
  [p addSubview:_encrypt];
  _password =
      makeInput(p, @"至少 8 位英文字母或数字；请妥善保存", NSMakeRect(260, 177, 430, 28), YES);
  _password.enabled = NO;
  makeLabel(p, @"排除规则", NSMakeRect(0, 134, 95, 24), 13);
  _exclude = makeInput(p, @"例如 *.tmp, .DS_Store, node_modules（逗号分隔）",
                       NSMakeRect(100, 133, 590, 28));
  _exclude.stringValue = @".DS_Store";
  makeLabel(p, @"文件名筛选", NSMakeRect(0, 91, 95, 24), 13);
  _name = makeInput(p, @"例如 *.txt；留空包含全部文件，目录始终保留", NSMakeRect(100, 90, 590, 28));
  makeLabel(p, @"压缩后更大时保留原始数据。备份文件必须保存在源目录之外。",
            NSMakeRect(100, 57, 700, 20), 11);
  [_actions addObject:makeButton(p, @"开始备份", NSMakeRect(100, 8, 160, 36), self,
                                 @selector(backup:), YES)];
}
- (void)buildRestore {
  NSView* p = _pages[1];
  makeLabel(p, @"恢复与验证", NSMakeRect(0, 340, 730, 30), 19, YES);
  makeLabel(p, @"备份文件", NSMakeRect(0, 295, 95, 24), 13);
  _readArchive = makeInput(p, @"选择已有 .sqbk 备份", NSMakeRect(100, 294, 590, 28));
  makeButton(p, @"打开…", NSMakeRect(700, 294, 100, 28), self, @selector(chooseArchive:));
  makeLabel(p, @"恢复到", NSMakeRect(0, 246, 95, 24), 13);
  _destination = makeInput(p, @"新文件夹的完整路径（不能已经存在）", NSMakeRect(100, 245, 590, 28));
  makeButton(p, @"选择位置…", NSMakeRect(700, 245, 100, 28), self, @selector(chooseRestore:));
  makeLabel(p, @"解密密码", NSMakeRect(0, 197, 95, 24), 13);
  _readPassword = makeInput(p, @"未加密的备份请留空", NSMakeRect(100, 196, 590, 28), YES);
  NSTextField* tip = makeLabel(p,
                               @"恢复前会自动检查完整性。密码错误或文件损坏时，恢复不会继续。\n"
                               @"请选择尚不存在的新文件夹，已有文件不会被覆盖。",
                               NSMakeRect(100, 115, 690, 60), 12);
  tip.maximumNumberOfLines = 3;
  tip.textColor = NSColor.secondaryLabelColor;
  [_actions addObject:makeButton(p, @"开始恢复", NSMakeRect(100, 45, 160, 36), self,
                                 @selector(restore:), YES)];
  [_actions addObject:makeButton(p, @"验证完整性", NSMakeRect(280, 45, 150, 36), self,
                                 @selector(verify:))];
  [_actions
      addObject:makeButton(p, @"查看内容", NSMakeRect(450, 45, 150, 36), self, @selector(list:))];
}
- (void)buildJobs {
  NSView* p = _pages[2];
  makeLabel(p, @"自动备份", NSMakeRect(0, 340, 730, 30), 19, YES);
  makeLabel(p, @"源目录", NSMakeRect(0, 298, 95, 24), 13);
  _jobSource = makeInput(p, @"选择自动备份的目录", NSMakeRect(100, 297, 590, 28));
  makeButton(p, @"选择…", NSMakeRect(700, 297, 100, 28), self, @selector(chooseJobSource:));
  makeLabel(p, @"存储目录", NSMakeRect(0, 256, 95, 24), 13);
  _repository =
      makeInput(p, @"已有的备份存储目录；必须在源目录之外", NSMakeRect(100, 255, 590, 28));
  makeButton(p, @"选择…", NSMakeRect(700, 255, 100, 28), self, @selector(chooseRepository:));
  makeLabel(p, @"间隔（秒）", NSMakeRect(0, 214, 95, 24), 13);
  _interval = makeInput(p, @"300", NSMakeRect(100, 213, 100, 28));
  _interval.stringValue = @"300";
  makeLabel(p, @"保留份数", NSMakeRect(240, 214, 95, 24), 13);
  _retention = makeInput(p, @"5", NSMakeRect(335, 213, 100, 28));
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
      makeInput(p, @"至少 8 位英文字母或数字；退出后不保存", NSMakeRect(260, 130, 430, 28), YES);
  _jobPassword.enabled = NO;
  makeLabel(p, @"每次启动使用独立任务目录，淘汰只清理本任务生成的备份。",
            NSMakeRect(100, 92, 700, 20), 11);
  makeLabel(p, @"任务需要保持应用运行；电脑休眠时暂停。源目录持续变化时会延迟备份。",
            NSMakeRect(100, 67, 700, 20), 11);
  [_actions addObject:makeButton(p, @"启动任务", NSMakeRect(100, 8, 160, 36), self,
                                 @selector(startJob:), YES)];
}
@end
