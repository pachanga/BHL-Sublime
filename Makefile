.PHONY: all package install clean

PKG_NAME := BHL-Sublime
PKG_FILES := BHL.sublime-syntax LSP-bhl.sublime-settings plugin.py .python-version README.md

all: package

package:
	@VERSION=$$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "0.0.0"); \
	zip -r $(PKG_NAME)-$$VERSION.sublime-package $(PKG_FILES)
	@echo "Built $$( ls -1 $(PKG_NAME)-*.sublime-package | tail -1 )"

install: package
	@FILE=$$(ls -1 $(PKG_NAME)-*.sublime-package | tail -1); \
	DEST="$$HOME/Library/Application Support/Sublime Text/Installed Packages/"; \
	cp "$$FILE" "$$DEST" && echo "Installed $$FILE"

clean:
	rm -f $(PKG_NAME)-*.sublime-package
