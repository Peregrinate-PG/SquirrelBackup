// Render Quick Look's actual PPTX preview HTML without showing or controlling a desktop window.
#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#include <cstdio>
@interface PreviewRenderer : NSObject <WKNavigationDelegate>
@property(nonatomic, strong) WKWebView* view;
@property(nonatomic, strong) NSArray<NSDictionary*>* rectangles;
@property(nonatomic, strong) NSString* output;
@property(nonatomic) NSInteger index;
@end
@implementation PreviewRenderer
- (void)webView:(WKWebView*)webView didFinishNavigation:(WKNavigation*)navigation {
  (void)navigation;
  [webView evaluateJavaScript:@"Array.from(document.querySelectorAll('div.slide')).map(e=>{const r=e.getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,w:r.width,h:r.height};})"
      completionHandler:^(id result, NSError* error) {
        if (error || ![result isKindOfClass:NSArray.class] || [result count] != 8) {
          fprintf(stderr,"Unexpected Quick Look slide geometry\n"); exit(1);
        }
        self.rectangles = result; self.index = 0; [self renderNext];
      }];
}
- (void)renderNext {
  if (self.index >= self.rectangles.count) { [NSApp stop:nil]; return; }
  NSDictionary* r = self.rectangles[self.index];
  WKPDFConfiguration* config = [[WKPDFConfiguration alloc] init];
  config.rect = CGRectMake([r[@"x"] doubleValue],[r[@"y"] doubleValue],
                           [r[@"w"] doubleValue],[r[@"h"] doubleValue]);
  [self.view createPDFWithConfiguration:config completionHandler:^(NSData* data,NSError* error) {
    NSString* filename = [NSString stringWithFormat:@"slide-%02ld.pdf",(long)self.index+1];
    if (error || ![data writeToFile:[self.output stringByAppendingPathComponent:filename] atomically:YES]) {
      fprintf(stderr,"PDF rendering failed\n");exit(1);
    }
    ++self.index; [self renderNext];
  }];
}
@end
int main(int argc,const char* argv[]) {
  if (argc != 3) return 2;
  @autoreleasepool {
    NSApplication* app = [NSApplication sharedApplication];
    [app setActivationPolicy:NSApplicationActivationPolicyProhibited];
    PreviewRenderer* renderer = [[PreviewRenderer alloc] init];
    renderer.output = [[NSString stringWithUTF8String:argv[2]] stringByStandardizingPath];
    [[NSFileManager defaultManager] createDirectoryAtPath:renderer.output withIntermediateDirectories:YES attributes:nil error:nil];
    renderer.view = [[WKWebView alloc] initWithFrame:NSMakeRect(0,0,1000,600)];
    renderer.view.navigationDelegate = renderer;
    NSURL* input = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
    [renderer.view loadFileURL:input allowingReadAccessToURL:input.URLByDeletingLastPathComponent];
    [app run];
  }
}
