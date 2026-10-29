// Copyright 2026 Squirrel Backup course project.
#include "gui_controller.h"
#include "gui_support.h"

using namespace squirrel;
using namespace squirrel::ui;

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
