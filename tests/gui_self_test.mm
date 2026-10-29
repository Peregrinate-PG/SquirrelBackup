// Copyright 2026 Squirrel Backup course project.
#include "gui_controller.h"
#include "gui_support.h"

#include <fstream>

using namespace squirrel;
using namespace squirrel::ui;

@implementation SquirrelController (SelfTest)
- (void)startSelfTest {
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
  if (![data writeToFile:toNSString((_testRoot / (toString(name) + ".pdf")).string())
              atomically:YES]) {
    throw Error("Could not write GUI evidence");
  }
  std::ofstream(_testRoot / "gui-events.txt") << toString(_logView.string);
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
        [self testCheck:parsePositiveInteger(@"8640000", 8640000, parsed) && parsed == 8640000
                message:"Maximum interval should be accepted"];
        for (NSString* invalid in @[
               @"", @"0", @"-1", @"1.5", @"1abc", @"1e3", @"8640001", @"99999999999999999999999999"
             ]) {
          [self testCheck:!parsePositiveInteger(invalid, 8640000, parsed)
                  message:"Invalid integer accepted"];
        }
        [self testCheck:!_stopButton.enabled message:"Stop should be disabled while idle"];
        [self stopJob:nil];
        [self testCheck:!_stop.load() message:"Idle stop should not alter state"];
        _jobSource.stringValue = toNSString((_testRoot / "source").string());
        _repository.stringValue = toNSString((_testRoot / "repository").string());
        _interval.stringValue = @"1.5";
        [self startJob:nil];
        [self testCheck:!_busy message:"Fractional interval must not start a job"];
        _interval.stringValue = @"300";
        [self backup:nil];
        [self testCheck:!_busy message:"Empty GUI inputs should not start a task"];
        _source.stringValue = toNSString((_testRoot / "source").string());
        _archive.stringValue = toNSString((_testRoot / "backup.sqbk").string());
        _encrypt.state = NSControlStateValueOn;
        [self encryptionChanged:nil];
        [self testCheck:_password.enabled message:"Encryption switch should enable password field"];
        _password.stringValue = @"gui-test-password";
        _jobPassword.stringValue = @"job-secret-must-not-save";
        _readPassword.stringValue = @"restore-secret-must-not-save";
        NSDictionary* settings = [self settings];
        [self testCheck:settings.count == 14 message:"Only whitelisted settings may be saved"];
        for (NSString* secret in
             @[ _password.stringValue, _jobPassword.stringValue, _readPassword.stringValue ]) {
          [self testCheck:![settings.allValues containsObject:secret]
                  message:"Password leaked into saved settings"];
        }
        [self backup:nil];
        [self testCheck:_busy message:"Backup should set busy state"];
        [self testCheck:!_actions.firstObject.enabled
                message:"Busy state should disable backup action"];
        [self testCheck:_stopButton.enabled message:"One-off backup must support cancellation"];
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
        _destination.stringValue = toNSString((_testRoot / "restored").string());
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
        _repository.stringValue = toNSString((_testRoot / "repository").string());
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
        _archive.stringValue = toNSString((_testRoot / "cancelled.sqbk").string());
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
        _repository.stringValue = toNSString((_testRoot / "watch-repository").string());
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

@end
