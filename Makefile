.PHONY: all package install clean

PKG_NAME := BHL-Sublime
PKG_FILES := BHL.sublime-syntax LSP-bhl.sublime-settings plugin.py debugger.py .python-version README.md

all: package

package:
	zip -r $(PKG_NAME).sublime-package $(PKG_FILES)
	@echo "Built $(PKG_NAME).sublime-package"

install: package
	cp "$(PKG_NAME).sublime-package" "$$HOME/Library/Application Support/Sublime Text/Installed Packages/" \
		&& echo "Installed $(PKG_NAME).sublime-package"

clean:
	rm -f $(PKG_NAME).sublime-package
