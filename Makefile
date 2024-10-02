NAME := sqlrepo
PDM := $(shell command -v pdm 2> /dev/null)

.DEFAULT_GOAL := install

.PHONY: install
install:
	@if [ -z $(PDM) ]; then echo "PDM could not be found."; exit 2; fi
	$(PDM) install -G:all --no-self


.PHONY: shell
shell:
	@if [ -z $(PDM) ]; then echo "PDM could not be found."; exit 2; fi
	$(ENV_VARS_PREFIX) $(PDM) run ipython --no-confirm-exit --no-banner --quick \
	--InteractiveShellApp.extensions="autoreload" \
	--InteractiveShellApp.exec_lines="%autoreload 2"

.PHONY: clean
clean:
	find . -type d -name "__pycache__" | xargs rm -rf {};
	rm -rf ./logs/*

.PHONY: lint
lint:
	@if [ -z $(PDM) ]; then echo "PDM could not be found."; exit 2; fi
	$(PDM) run pyright $(NAME)
	$(PDM) run black --config ./pyproject.toml --check $(NAME) --diff
	$(PDM) run ruff check $(NAME)
	$(PDM) run vulture $(NAME) --min-confidence 100 --exclude "*/types.py,*/logger.py"

.PHONY: fix
fix:
	@if [ -z $(PDM) ]; then echo "PDM could not be found."; exit 2; fi
	$(PDM) run ruff check $(NAME) --config ./pyproject.toml --fix
	$(PDM) run black --config ./pyproject.toml $(NAME)

.PHONY: tests
tests:
	@if [ -z $(PDM) ]; then echo "PDM could not be found."; exit 2; fi
	$(PDM) run coverage run -m pytest -vv
	$(PDM) run coverage xml
	$(PDM) run coverage report --fail-under=95
