// Copyright 2026 Squirrel Backup course project.
#include "gui_controller.h"
#include "gui_support.h"

#include <chrono>
#include <memory>

using namespace squirrel;
using namespace squirrel::ui;

@implementation SquirrelController
// Only these explicit non-sensitive fields are persisted. Passwords never enter defaults.
- (NSDictionary*)settings {
  return @{
    @"source" : _source.stringValue,
    @"archive" : _archive.stringValue,
    @"exclude" : _exclude.stringValue,
    @"name" : _name.stringValue,
    @"readArchive" : _readArchive.stringValue,
    @"destination" : _destination.stringValue,
    @"jobSource" : _jobSource.stringValue,
    @"repository" : _repository.stringValue,
    @"interval" : _interval.stringValue,
    @"retention" : _retention.stringValue,
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
  NSDictionary* settings =
      [NSUserDefaults.standardUserDefaults dictionaryForKey:@"SquirrelBackup.FormSettings.v1"];
  NSDictionary* fields = @{
    @"source" : _source,
    @"archive" : _archive,
    @"exclude" : _exclude,
    @"name" : _name,
    @"readArchive" : _readArchive,
    @"destination" : _destination,
    @"jobSource" : _jobSource,
    @"repository" : _repository,
    @"interval" : _interval,
    @"retention" : _retention
  };
  for (NSString* key in fields) {
    if ([settings[key] isKindOfClass:NSString.class]) {
      ((NSTextField*)fields[key]).stringValue = settings[key];
    }
  }
  NSDictionary* switches = @{
    @"compress" : _compress,
    @"encrypt" : _encrypt,
    @"watch" : _watch,
    @"jobEncrypt" : _jobEncrypt
  };
  for (NSString* key in switches) {
    if ([settings[key] isKindOfClass:NSNumber.class]) {
      ((NSButton*)switches[key]).state =
          [settings[key] boolValue] ? NSControlStateValueOn : NSControlStateValueOff;
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
  return Operation{
      &_stop, [self, state](const ProgressInfo& info) {
        auto now = std::chrono::steady_clock::now();
        if (state->phase == info.phase && now - state->last < std::chrono::milliseconds(150)) {
          return;
        }
        state->last = now;
        state->phase = info.phase;
        NSString* title = phaseName(info.phase);
        if (info.total) {
          if (info.phase == Phase::Metadata) {
            title = [NSString
                stringWithFormat:@"%@ · %llu / %llu 项", title, info.completed, info.total];
          } else {
            title = [NSString stringWithFormat:@"%@ · %@ / %@", title, byteCount(info.completed),
                                               byteCount(info.total)];
          }
        } else if (info.phase == Phase::Scan && info.completed) {
          title = [NSString stringWithFormat:@"%@ · 已发现 %llu 项", title, info.completed];
        }
        NSString* path = toNSString(info.path);
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
      result = toNSString(work());
    } catch (const Cancelled&) {
      cancelled = YES;
      result = @"操作已取消，未完成的临时文件已清理。";
    } catch (const std::exception& e) {
      success = NO;
      result = [NSString
          stringWithFormat:@"%@\n详细原因：%@", errorExplanation(e.what()), toNSString(e.what())];
    }
    dispatch_async(dispatch_get_main_queue(), ^{
      self->_busy = NO;
      self->_jobRunning = NO;
      self->_stopButton.enabled = NO;
      [self->_progress stopAnimation:nil];
      [self setInputsEnabled:YES];
      self->_currentPath.stringValue = @"";
      self->_status.stringValue = cancelled  ? @"已取消"
                                  : !success ? @"未完成 · 请查看下方原因"
                                  : wasJob   ? @"已停止"
                                             : @"已完成";
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
  std::string source = toString(_source.stringValue), archive = toString(_archive.stringValue);
  if (source.empty() || archive.empty()) {
    [self appendLog:@"请先填写源目录和备份文件路径。"];
    return;
  }
  BackupOptions options;
  options.compress = _compress.state == NSControlStateValueOn;
  if (_encrypt.state == NSControlStateValueOn) {
    options.password = toString(_password.stringValue);
    if (options.password.size() < 8) {
      [self appendLog:@"加密密码至少需要 8 字节。"];
      return;
    }
  }
  for (NSString* raw in [_exclude.stringValue componentsSeparatedByString:@","]) {
    NSString* s = [raw stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
    if (s.length) {
      options.filter.excludes.push_back(toString(s));
    }
  }
  options.filter.name_pattern = toString(_name.stringValue);
  Log log = [self logger];
  Operation operation = [self operation];
  [self perform:@"正在备份…"
           work:[=] {
             auto summary = BackupService{}.backup(source, archive, options, log, operation);
             dispatch_async(dispatch_get_main_queue(), ^{
               self->_readArchive.stringValue = toNSString(archive);
             });
             return summaryText(summary);
           }];
}
- (void)readAction:(SquirrelReadAction)mode {
  std::string archive = toString(_readArchive.stringValue),
              dest = toString(_destination.stringValue),
              password = toString(_readPassword.stringValue);
  if (archive.empty() || (mode == SquirrelReadAction::Restore && dest.empty())) {
    [self appendLog:@"请先填写备份文件路径；恢复操作还需填写新文件夹路径。"];
    return;
  }
  Log log = [self logger];
  Operation operation = [self operation];
  [self perform:mode == SquirrelReadAction::Restore ? @"正在验证并恢复…" : @"正在验证备份…"
           work:[=] {
             Summary result =
                 mode == SquirrelReadAction::Restore
                     ? BackupService{}.restore(archive, dest, password, log, operation)
                     : BackupService{}.inspect(archive, password, log,
                                               mode == SquirrelReadAction::List, operation);
             if (mode == SquirrelReadAction::List) {
               size_t shown = 0;
               for (const auto& e : result.items) {
                 if (++shown > 300) {
                   log("更多条目请使用 CLI list 查看。");
                   break;
                 }
                 log(typeName(e.type) + "  " + (e.path.empty() ? "." : e.path));
               }
             }
             return summaryText(result);
           }];
}
- (void)restore:(id)sender {
  (void)sender;
  [self readAction:SquirrelReadAction::Restore];
}
- (void)verify:(id)sender {
  (void)sender;
  [self readAction:SquirrelReadAction::Verify];
}
- (void)list:(id)sender {
  (void)sender;
  [self readAction:SquirrelReadAction::List];
}
- (void)startJob:(id)sender {
  (void)sender;
  if (_busy) {
    return;
  }
  auto source = toString(_jobSource.stringValue), repo = toString(_repository.stringValue);
  uint32_t interval = 0, keep = 0;
  bool watch = _watch.state == NSControlStateValueOn;
  if (source.empty() || repo.empty() ||
      (!watch && !parsePositiveInteger(_interval.stringValue, 8640000, interval)) ||
      !parsePositiveInteger(_retention.stringValue, 10000, keep)) {
    [self appendLog:@"请检查目录；间隔须为 1–8640000 的整数，保留份数须为 1–10000 的整数。"];
    return;
  }
  BackupOptions options;
  if (_jobEncrypt.state == NSControlStateValueOn) {
    options.password = toString(_jobPassword.stringValue);
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
