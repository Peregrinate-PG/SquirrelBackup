CXX := clang++
export MACOSX_DEPLOYMENT_TARGET := 13.0
BUILD ?= build
CPPFLAGS := -Iinclude -Isrc
CXXFLAGS := -std=c++17 -O2 -g -Wall -Wextra -Wpedantic -Werror -Wno-deprecated-declarations
LDLIBS := -framework Security
CORE := huffman scanner crypto archive service scheduler
OBJECTS := $(addprefix $(BUILD)/,$(addsuffix .o,$(CORE)))
GTEST := $(if $(wildcard vendor/googletest/googletest),vendor/googletest/googletest,.tools/src/googletest/googletest)
.PHONY: all cli app test sanitize lint clean package fuzz
all: cli app
cli: $(BUILD)/squirrel
$(BUILD):
	mkdir -p $@
$(BUILD)/%.o: src/%.cpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c $< -o $@
$(BUILD)/libsquirrel.a: $(OBJECTS)
	ar rcs $@ $^
$(BUILD)/squirrel: $(BUILD)/cli.o $(BUILD)/libsquirrel.a
	$(CXX) $(CXXFLAGS) $^ $(LDLIBS) -o $@
$(BUILD)/SquirrelBackup.app/Contents/MacOS/SquirrelBackup: src/gui.mm $(BUILD)/libsquirrel.a resources/Info.plist
	mkdir -p $(BUILD)/SquirrelBackup.app/Contents/MacOS $(BUILD)/SquirrelBackup.app/Contents/Resources
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -fobjc-arc src/gui.mm $(BUILD)/libsquirrel.a -framework Cocoa $(LDLIBS) -o $@
	cp resources/Info.plist $(BUILD)/SquirrelBackup.app/Contents/Info.plist
	codesign --force --sign - $(BUILD)/SquirrelBackup.app
app: $(BUILD)/SquirrelBackup.app/Contents/MacOS/SquirrelBackup
$(BUILD)/gtest-all.o: $(GTEST)/src/gtest-all.cc | $(BUILD)
	$(CXX) -std=c++17 -O1 -g -I$(GTEST)/include -I$(GTEST) -c $< -o $@
$(BUILD)/tests: tests/core_test.cpp $(BUILD)/libsquirrel.a $(BUILD)/gtest-all.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -isystem $(GTEST)/include tests/core_test.cpp $(BUILD)/libsquirrel.a $(BUILD)/gtest-all.o $(GTEST)/src/gtest_main.cc $(LDLIBS) -o $@
test: $(BUILD)/tests $(BUILD)/squirrel
	mkdir -p test-results
	$(BUILD)/tests --gtest_output=xml:test-results/unit.xml
	python3 tests/integration.py $(BUILD)/squirrel
	python3 tests/adversarial.py $(BUILD)/squirrel
	python3 tests/workflow_regression.py $(BUILD)/squirrel
sanitize:
	$(MAKE) BUILD=build/sanitize CXXFLAGS='-std=c++17 -O1 -g -Wall -Wextra -Werror -Wno-deprecated-declarations -fsanitize=address,undefined -fno-omit-frame-pointer' test
$(BUILD)/huffman_fuzz: tests/huffman_fuzz.cpp tests/fuzz_driver.cpp src/huffman.cpp include/squirrel/backup.h | $(BUILD)
	$(CXX) -std=c++17 -O1 -g -Iinclude -fsanitize=address,undefined tests/huffman_fuzz.cpp tests/fuzz_driver.cpp src/huffman.cpp -o $@
fuzz: $(BUILD)/huffman_fuzz
	mkdir -p test-results
	$(BUILD)/huffman_fuzz test-results/fuzz.json 60 > test-results/fuzz.log 2>&1
lint:
	.tools/venv/bin/cpplint --linelength=100 --root=include --filter=-build/c++17,-build/header_guard,-build/namespaces,-build/include_order,-build/include_subdir,-runtime/references include/squirrel/backup.h src/*.cpp src/internal.h tests/*.cpp
package: all
	bash scripts/package.sh
clean:
	rm -rf $(BUILD)
-include $(wildcard $(BUILD)/*.d)
