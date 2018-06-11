flake8:
	flake8
reformat:
	black `git ls-files "*.py"`
stylecheck:
	black --check --diff `git ls-files "*.py"`
