// Copyright 2026 Squirrel Backup course project.
#include <fstream>
#include "gui_controller.h"
#include "gui_support.h"

using namespace squirrel;
using namespace squirrel::ui;

#import <AVFoundation/AVFoundation.h>
#import <CoreVideo/CoreVideo.h>
#include <sys/stat.h>
#include <unistd.h>
#include <iostream>
namespace {
void require(bool condition, const std::string& message) {
  if (!condition) {
    throw squirrel::Error(message);
  }
}
}  // namespace
@interface SquirrelDemoController : SquirrelController {
  AVAssetWriter* _writer;
  AVAssetWriterInput* _video;
  AVAssetWriterInputPixelBufferAdaptor* _adaptor;
  NSDate* _began;
  NSString *_caption, *_heading;
  int _phase, _frames;
  double _lastFrame;
  NSMutableArray* _events;
  BOOL _finishing;
}
@end
@implementation SquirrelDemoController
- (void)applicationDidFinishLaunching:(NSNotification*)notification {
  [super applicationDidFinishLaunching:notification];
  std::ofstream(_testRoot / "source" / "项目说明.txt")
      << "Squirrel Backup demo: original content.\n";
  fs::create_directory(_testRoot / "source" / "空目录");
  std::string block(1024 * 1024, 'S');
  std::ofstream large(_testRoot / "source" / "重复数据.bin", std::ios::binary);
  for (int i = 0; i < 32; ++i) {
    large.write(block.data(), block.size());
  }
  large.close();
  fs::create_symlink("项目说明.txt", _testRoot / "source" / "说明链接");
  fs::create_hard_link(_testRoot / "source" / "项目说明.txt", _testRoot / "source" / "说明硬链接");
  require(mkfifo((_testRoot / "source" / "示例管道").c_str(), 0600) == 0, "FIFO fixture failed");
  _source.stringValue = toNSString((_testRoot / "source").string());
  _archive.stringValue = toNSString((_testRoot / "课程演示.sqbk").string());
  _encrypt.state = NSControlStateValueOn;
  _password.stringValue = @"squirrel-demo-2026";
  [self encryptionChanged:nil];
  _events = [NSMutableArray array];
  _heading = @"创建加密备份";
  _caption = @"演示数据包含中文文件、空目录、软硬链接、FIFO与32 MiB重复数据。";
  NSError* error = nil;
  _writer = [[AVAssetWriter alloc]
      initWithURL:[NSURL fileURLWithPath:toNSString((_testRoot / "松鼠备份_后台演示.mp4").string())]
         fileType:AVFileTypeMPEG4
            error:&error];
  require(_writer != nil, toString(error.localizedDescription));
  _video = [AVAssetWriterInput assetWriterInputWithMediaType:AVMediaTypeVideo
                                              outputSettings:@{
                                                AVVideoCodecKey : AVVideoCodecTypeH264,
                                                AVVideoWidthKey : @1440,
                                                AVVideoHeightKey : @1080,
                                                AVVideoCompressionPropertiesKey : @{
                                                  AVVideoAverageBitRateKey : @4500000,
                                                  AVVideoExpectedSourceFrameRateKey : @5,
                                                  AVVideoMaxKeyFrameIntervalKey : @10
                                                }
                                              }];
  _video.expectsMediaDataInRealTime = YES;
  _adaptor = [AVAssetWriterInputPixelBufferAdaptor
      assetWriterInputPixelBufferAdaptorWithAssetWriterInput:_video
                                 sourcePixelBufferAttributes:@{
                                   (id)
                                   kCVPixelBufferPixelFormatTypeKey : @(kCVPixelFormatType_32BGRA),
                                   (id)kCVPixelBufferWidthKey : @1440,
                                   (id)kCVPixelBufferHeightKey : @1080,
                                   (id)kCVPixelBufferCGImageCompatibilityKey : @YES,
                                   (id)kCVPixelBufferCGBitmapContextCompatibilityKey : @YES
                                 }];
  require([_writer canAddInput:_video], "Video input rejected");
  [_writer addInput:_video];
  require([_writer startWriting], toString(_writer.error.localizedDescription));
  [_writer startSessionAtSourceTime:kCMTimeZero];
  _began = NSDate.date;
  _lastFrame = -1;
  [self appendLog:@"演示开始：全部数据位于独立测试目录。"];
}
- (void)event:(NSString*)name {
  [_events addObject:@{
    @"event" : name,
    @"elapsed_seconds" : @([NSDate.date timeIntervalSinceDate:_began])
  }];
}
- (void)recordFrame:(double)t {
  if (!_video.readyForMoreMediaData || t - _lastFrame < .19) {
    return;
  }
  CVPixelBufferRef pixel = NULL;
  require(CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, _adaptor.pixelBufferPool,
                                             &pixel) == kCVReturnSuccess,
          "Pixel allocation failed");
  CVPixelBufferLockBaseAddress(pixel, 0);
  CGColorSpaceRef color = CGColorSpaceCreateDeviceRGB();
  CGContextRef ctx = CGBitmapContextCreate(
      CVPixelBufferGetBaseAddress(pixel), 1440, 1080, 8, CVPixelBufferGetBytesPerRow(pixel), color,
      kCGBitmapByteOrder32Little | kCGImageAlphaPremultipliedFirst);
  CGColorSpaceRelease(color);
  require(ctx != NULL, "Frame context failed");
  CGContextSetRGBFillColor(ctx, .965, .965, .95, 1);
  CGContextFillRect(ctx, CGRectMake(0, 0, 1440, 1080));
  NSData* pdf = [_window.contentView dataWithPDFInsideRect:_window.contentView.bounds];
  CGDataProviderRef provider = CGDataProviderCreateWithCFData((__bridge CFDataRef)pdf);
  CGPDFDocumentRef doc = CGPDFDocumentCreateWithProvider(provider);
  CGPDFPageRef page = CGPDFDocumentGetPage(doc, 1);
  CGContextSaveGState(ctx);
  CGContextConcatCTM(ctx, CGPDFPageGetDrawingTransform(page, kCGPDFMediaBox,
                                                       CGRectMake(180, 156, 1080, 790), 0, YES));
  CGContextDrawPDFPage(ctx, page);
  CGContextRestoreGState(ctx);
  CGPDFDocumentRelease(doc);
  CGDataProviderRelease(provider);
  [NSGraphicsContext saveGraphicsState];
  [NSGraphicsContext setCurrentContext:[NSGraphicsContext graphicsContextWithCGContext:ctx
                                                                               flipped:NO]];
  NSColor* ink = [NSColor colorWithSRGBRed:.14 green:.18 blue:.20 alpha:1];
  [@"松鼠备份 0.2.0 · 第3组" drawInRect:NSMakeRect(80, 1008, 1280, 48)
                         withAttributes:@{
                           NSFontAttributeName : [NSFont boldSystemFontOfSize:32],
                           NSForegroundColorAttributeName : ink
                         }];
  [_heading drawInRect:NSMakeRect(80, 957, 1280, 42)
        withAttributes:@{
          NSFontAttributeName : [NSFont systemFontOfSize:26 weight:NSFontWeightMedium],
          NSForegroundColorAttributeName : ink
        }];
  [_caption drawInRect:NSMakeRect(80, 63, 1280, 76)
        withAttributes:@{
          NSFontAttributeName : [NSFont systemFontOfSize:25],
          NSForegroundColorAttributeName : ink
        }];
  NSString* footer =
      [NSString stringWithFormat:@"真实应用后台演示 · 自动触发按钮处理流程 · %02d:%02d",
                                 (int)t / 60, (int)t % 60];
  [footer drawInRect:NSMakeRect(80, 20, 1280, 32)
      withAttributes:@{
        NSFontAttributeName : [NSFont systemFontOfSize:18],
        NSForegroundColorAttributeName : NSColor.darkGrayColor
      }];
  [NSGraphicsContext restoreGraphicsState];
  if (_frames % 25 == 0) {
    CGImageRef image = CGBitmapContextCreateImage(ctx);
    NSBitmapImageRep* rep = [[NSBitmapImageRep alloc] initWithCGImage:image];
    [[rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}]
        writeToFile:toNSString((_testRoot / ("frame-" + std::to_string(_frames) + ".png")).string())
         atomically:YES];
    CGImageRelease(image);
  }
  CGContextRelease(ctx);
  CVPixelBufferUnlockBaseAddress(pixel, 0);
  BOOL ok = [_adaptor appendPixelBuffer:pixel withPresentationTime:CMTimeMakeWithSeconds(t, 600)];
  CVPixelBufferRelease(pixel);
  require(ok, toString(_writer.error.localizedDescription));
  _lastFrame = t;
  ++_frames;
}
- (int)snapshotCount:(const fs::path&)repo {
  int count = 0;
  for (const auto& e : fs::recursive_directory_iterator(repo)) {
    if (e.path().extension() == ".sqbk") {
      ++count;
    }
  }
  return count;
}
- (void)selfTestTick:(NSTimer*)timer {
  if (_finishing) {
    return;
  }
  @autoreleasepool {
    try {
      double t = [NSDate.date timeIntervalSinceDate:_began];
      require(t < 119, "Demo exceeded 2 minutes");
      switch (_phase) {
        case 0:
          if (t < 6) {
            break;
          }
          [self backup:nil];
          [self event:@"backup_started"];
          ++_phase;
          break;
        case 1:
          if (t < 16 || _busy) {
            break;
          }
          require(fs::exists(_testRoot / "课程演示.sqbk"), "Backup not published");
          [self event:@"backup_published"];
          _heading = @"验证与查看内容";
          _caption = @"备份先完成压缩，再使用密码加密；验证会检查归档结构和完整性。";
          [self showPage:1];
          _readPassword.stringValue = _password.stringValue;
          _destination.stringValue = toNSString((_testRoot / "恢复副本").string());
          [self verify:nil];
          ++_phase;
          break;
        case 2:
          if (t < 25 || _busy) {
            break;
          }
          require([_status.stringValue isEqualToString:@"已完成"], "Verify failed");
          [self list:nil];
          [self event:@"verification_passed"];
          ++_phase;
          break;
        case 3:
          if (t < 34 || _busy) {
            break;
          }
          _heading = @"错误密码不会生成恢复目录";
          _caption = @"输入另一密码尝试恢复，程序拒绝继续；原备份保留，目标目录不存在。";
          _readPassword.stringValue = @"incorrect-demo-password";
          [self restore:nil];
          ++_phase;
          break;
        case 4:
          if (t < 44 || _busy) {
            break;
          }
          require(
              !fs::exists(_testRoot / "恢复副本") && [_status.stringValue containsString:@"未完成"],
              "Wrong-password protection failed");
          [self event:@"wrong_password_rejected"];
          _heading = @"恢复到新目录并核对内容";
          _caption = @"改用正确密码恢复。完成后比对原文件内容，并检查软硬链接和FIFO。";
          _readPassword.stringValue = _password.stringValue;
          [self restore:nil];
          ++_phase;
          break;
        case 5: {
          if (t < 55 || _busy) {
            break;
          }
          auto restored = _testRoot / "恢复副本";
          require(fs::exists(restored / "项目说明.txt"), "Restore missing");
          for (const char* name : {"项目说明.txt", "重复数据.bin", "中文.txt"}) {
            std::ifstream a(_testRoot / "source" / name, std::ios::binary),
                b(restored / name, std::ios::binary);
            std::string av{std::istreambuf_iterator<char>(a), {}},
                bv{std::istreambuf_iterator<char>(b), {}};
            require(av == bv, "Restored bytes mismatch");
          }
          require(fs::read_symlink(restored / "说明链接") == "项目说明.txt", "Symlink mismatch");
          struct stat a {
          }, b{}, fifo{};
          stat((restored / "项目说明.txt").c_str(), &a);
          stat((restored / "说明硬链接").c_str(), &b);
          require(a.st_ino == b.st_ino, "Hardlink mismatch");
          lstat((restored / "示例管道").c_str(), &fifo);
          require(S_ISFIFO(fifo.st_mode), "FIFO mismatch");
          [self appendLog:@"演示核对通过：文件逐字节一致，软链接、硬链接与FIFO类型正确。"];
          [self event:@"restore_bytes_and_links_passed"];
          _caption = @"核对通过：普通文件逐字节一致，链接关系和FIFO类型保留。";
          ++_phase;
          break;
        }
        case 6:
          if (t < 61) {
            break;
          }
          _heading = @"定时备份与保留数量";
          _caption = @"每3秒生成完整快照，只保留本任务最近2份；旧快照淘汰会显示在日志中。";
          [self showPage:2];
          _jobSource.stringValue = _source.stringValue;
          _repository.stringValue = toNSString((_testRoot / "repository").string());
          _interval.stringValue = @"3";
          _retention.stringValue = @"2";
          [self startJob:nil];
          [self event:@"schedule_started"];
          ++_phase;
          break;
        case 7:
          if (t < 77) {
            break;
          }
          require([self snapshotCount:_testRoot / "repository"] == 2 &&
                      [_logView.string containsString:@"已淘汰旧快照"],
                  "Retention not observed");
          [self event:@"retention_two_confirmed"];
          [self stopJob:nil];
          ++_phase;
          break;
        case 8:
          if (t < 83 || _busy) {
            break;
          }
          [self event:@"schedule_stopped"];
          _heading = @"目录变化后自动备份";
          _caption = @"开启变化检测后修改演示文件；等待变化稳定，再生成新快照。";
          _watch.state = NSControlStateValueOn;
          [self watchChanged:nil];
          fs::create_directory(_testRoot / "watch-repository");
          _repository.stringValue = toNSString((_testRoot / "watch-repository").string());
          [self startJob:nil];
          ++_phase;
          break;
        case 9:
          if (t < 91) {
            break;
          }
          require([self snapshotCount:_testRoot / "watch-repository"] >= 1,
                  "Watch initial missing");
          std::ofstream(_testRoot / "source" / "变化记录.txt")
              << "Revision created during real watch demonstration.\n";
          [self event:@"source_file_added"];
          ++_phase;
          break;
        case 10:
          if (t < 101) {
            break;
          }
          require([self snapshotCount:_testRoot / "watch-repository"] == 2, "Watch change missing");
          [self event:@"watch_change_snapshot_confirmed"];
          [self stopJob:nil];
          ++_phase;
          break;
        case 11:
          if (t < 105 || _busy) {
            break;
          }
          [self event:@"watch_stopped"];
          _heading = @"取消未完成操作";
          _caption = @"新建一次备份后请求取消。未完成输出与临时文件清理，已完成的备份保留。";
          [self showPage:0];
          _archive.stringValue = toNSString((_testRoot / "取消示例.sqbk").string());
          [self backup:nil];
          [self stopJob:nil];
          ++_phase;
          break;
        case 12:
          if (t < 109 || _busy) {
            break;
          }
          require(!fs::exists(_testRoot / "取消示例.sqbk") &&
                      [_status.stringValue isEqualToString:@"已取消"],
                  "Cancellation failed");
          [self event:@"cancelled_output_absent"];
          _heading = @"演示完成";
          _caption = @"已展示备份、验证、恢复、错误密码、定时保留、变化检测与停止。完整操作日志随视"
                     @"频保存。";
          ++_phase;
          break;
        case 13:
          if (t < 115) {
            break;
          }
          [self event:@"demo_finished"];
          [timer invalidate];
          _finishing = YES;
          [self recordFrame:t];
          [_video markAsFinished];
          [_writer endSessionAtSourceTime:CMTimeMakeWithSeconds(t, 600)];
          [_writer finishWritingWithCompletionHandler:^{
            dispatch_async(dispatch_get_main_queue(), ^{
              if (self->_writer.status != AVAssetWriterStatusCompleted) {
                std::exit(1);
              }
              NSDictionary* result = @{
                @"passed" : @YES,
                @"seconds" : @(t),
                @"frames" : @(self->_frames),
                @"method" : @"real offscreen AppKit view; automated production handlers; no "
                            @"mouse/system picker",
                @"events" : self->_events
              };
              [[NSJSONSerialization dataWithJSONObject:result
                                               options:NSJSONWritingPrettyPrinted
                                                 error:nil]
                  writeToFile:toNSString((self->_testRoot / "demo-evidence.json").string())
                   atomically:YES];
              std::ofstream(self->_testRoot / "demo-events.txt") << toString(self->_logView.string);
              [NSApp terminate:nil];
            });
          }];
          return;
      }
      [self recordFrame:t];
    } catch (const std::exception& e) {
      std::ofstream(_testRoot / "demo-error.txt") << e.what();
      [self stopJob:nil];
      [_writer cancelWriting];
      std::exit(1);
    }
  }
}
@end
int main(int argc, const char* argv[]) {
  if (argc != 2) {
    return 2;
  }
  selfTestDirectory = argv[1];
  if (fs::exists(selfTestDirectory)) {
    std::cerr << "Use a new isolated demo directory\n";
    return 2;
  }
  @autoreleasepool {
    NSApplication* app = NSApplication.sharedApplication;
    [app setActivationPolicy:NSApplicationActivationPolicyProhibited];
    SquirrelDemoController* controller = [[SquirrelDemoController alloc] init];
    app.delegate = controller;
    [app run];
  }
  return 0;
}
