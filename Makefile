.PHONY: install

install:
	mkdir -p ~/.local/bin
	cp ./issue.py ~/.local/bin/issue
	chmod +x ~/.local/bin/issue
	mkdir -p ~/.local/share/issue
	cp ./ui.json ~/.local/share/issue/ui.json
	cp ./share/issue_message ~/.local/share/issue/issue_message
