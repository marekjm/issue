PYTHONVERSION=`python3 -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))'`

PREFIX=~/.local
BIN_DIR=$(PREFIX)/bin
LIB_DIR=$(PREFIX)/lib/python$(PYTHONVERSION)/site-packages
SHARE_DIR=$(PREFIX)/share

.PHONY: install

install:
	mkdir -p $(BIN_DIR)
	cp ./issue.py $(BIN_DIR)/issue
	chmod +x $(BIN_DIR)/issue
	mkdir -p $(SHARE_DIR)/issue
	cp ./ui.json $(SHARE_DIR)/issue/ui.json
	cp ./share/*_message $(SHARE_DIR)/issue/
	mkdir -p $(LIB_DIR)/issue
	cp -R ./issue/* $(LIB_DIR)/issue/
	sed -i 's/\<HEAD\>/$(shell git rev-parse HEAD)/' $(LIB_DIR)/issue/__init__.py
