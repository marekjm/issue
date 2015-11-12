PYTHONVERSION=`python3 -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))'`

.PHONY: install

install:
	mkdir -p ~/.local/bin
	cp ./issue.py ~/.local/bin/issue
	chmod +x ~/.local/bin/issue
	mkdir -p ~/.local/share/issue
	cp ./ui.json ~/.local/share/issue/ui.json
	cp ./share/*_message ~/.local/share/issue/
	mkdir -p ~/.local/lib/python$(PYTHONVERSION)/site-packages/issue
	cp -R ./issue/. ~/.local/lib/python$(PYTHONVERSION)/site-packages/issue/
