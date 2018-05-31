flake8:
	flake8 `git ls-files "*.py"`
reformat:
	black `git ls-files "*.py"`
stylecheck:
	black --check --diff `git ls-files "*.py"`
