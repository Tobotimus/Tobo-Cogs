PYTHON ?= python3.7

flake8:
	$(PYTHON) -m flake8
reformat:
	$(PYTHON) -m black `git ls-files "*.py"`
stylecheck:
	$(PYTHON) -m black --check --diff `git ls-files "*.py"`
