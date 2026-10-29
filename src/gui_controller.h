// Copyright 2026 Squirrel Backup course project.
#ifndef SQUIRREL_GUI_CONTROLLER_H_
#define SQUIRREL_GUI_CONTROLLER_H_

#import <Cocoa/Cocoa.h>
#include "squirrel/backup.h"

enum class SquirrelReadAction { Restore, Verify, List };

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
  squirrel::fs::path _testRoot;
  NSDate* _testStarted;
}
- (NSDictionary*)settings;
- (void)saveSettings;
- (void)loadSettings;
- (void)appendLog:(NSString*)line;
- (void)showPage:(NSInteger)index;
- (void)navigate:(NSButton*)sender;
- (void)encryptionChanged:(id)sender;
- (void)watchChanged:(id)sender;
- (NSString*)chooseDirectory;
- (void)chooseSource:(id)sender;
- (void)chooseJobSource:(id)sender;
- (void)chooseRepository:(id)sender;
- (void)chooseOutput:(id)sender;
- (void)chooseArchive:(id)sender;
- (void)chooseRestore:(id)sender;
- (squirrel::Log)logger;
- (squirrel::Operation)operation;
- (void)setInputsEnabled:(BOOL)enabled;
- (void)perform:(NSString*)title work:(std::function<std::string()>)work;
- (void)backup:(id)sender;
- (void)readAction:(SquirrelReadAction)mode;
- (void)restore:(id)sender;
- (void)verify:(id)sender;
- (void)list:(id)sender;
- (void)startJob:(id)sender;
- (void)stopJob:(id)sender;
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication*)sender;
- (BOOL)windowShouldClose:(NSWindow*)sender;
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication*)sender;
@end

@interface SquirrelController (Layout)
- (void)applicationDidFinishLaunching:(NSNotification*)notification;
- (void)buildBackup;
- (void)buildRestore;
- (void)buildJobs;
@end

@interface SquirrelController (SelfTest)
- (void)startSelfTest;
- (void)testCheck:(BOOL)condition message:(const char*)message;
- (void)captureEvidence:(NSString*)name page:(NSInteger)page;
- (void)selfTestTick:(NSTimer*)timer;
@end

#endif  // SQUIRREL_GUI_CONTROLLER_H_
