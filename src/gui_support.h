// Copyright 2026 Squirrel Backup course project.
#ifndef SQUIRREL_GUI_SUPPORT_H_
#define SQUIRREL_GUI_SUPPORT_H_

#import <Cocoa/Cocoa.h>
#include "squirrel/backup.h"

namespace squirrel::ui {
extern std::string previewDirectory;
extern std::string selfTestDirectory;
extern int previewPage;
NSColor* accent();
NSString* toNSString(const std::string& text);
std::string toString(NSString* text);
NSTextField* makeLabel(NSView* parent, NSString* text, NSRect frame, CGFloat size, BOOL bold = NO);
NSTextField* makeInput(NSView* parent, NSString* placeholder, NSRect frame, BOOL secure = NO);
NSButton* makeButton(NSView* parent, NSString* title, NSRect frame, id target, SEL action,
                     BOOL primary = NO);
bool parsePositiveInteger(NSString* text, uint32_t maximum, uint32_t& result);
std::string summaryText(const Summary& summary);
NSString* byteCount(uint64_t bytes);
NSString* phaseName(Phase phase);
NSString* errorExplanation(const std::string& error);
NSString* displayLog(const std::string& message);
}  // namespace squirrel::ui

#endif  // SQUIRREL_GUI_SUPPORT_H_
