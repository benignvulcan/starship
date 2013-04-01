#!/usr/bin/make
# GNU Makefile

PYTHON=python

all: starshipMainWindow_ui.py unittest

.PHONY: unittest clean

# Implicit/Pattern rule for compiling .ui files to Python
%_ui.py : %.ui
	pyuic4 -o $@ $<

unittest:
	$(PYTHON) -c 'import sys; sys.exit(sys.hexversion < 0x02060000)'
	$(PYTHON) qtmath.py
	$(PYTHON) vexor.py
	$(PYTHON) scheduler.py
	$(PYTHON) simulation.py
	$(PYTHON) starship.py --unittest

clean:
	rm -f *.pyc *.pyo *_ui.py *~

