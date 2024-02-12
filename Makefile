NAME := sqlrepo
POETRY := $(shell command -v poetry 2> /dev/null)

.DEFAULT_GOAL := help
mode ?= dev
message ?= default message
ENV_VARS_PREFIX := PROJECT_RUN_MODE="$(mode)"

.PHONY: help
help:
	@echo -e "Пожалуйста, испольйте \033[0;33m'make <target>'\033[0m где <target> одна из"
	@echo ""
	@echo -e "  \033[0;33mrun\033[0m             запускает проект"
	@echo -e "  \033[0;33minstall\033[0m         запускает установку пакеты и подготовку окружение"
	@echo -e "  \033[0;33mshell\033[0m           запускает ipython оболочку"
	@echo -e "  \033[0;33mclean\033[0m           запускает удаление всех временных файлов"
	@echo -e "  \033[0;33mlint\033[0m            запускает проверку кода"
	@echo -e "  \033[0;33mformat\033[0m          запускает форматирование кода"
	@echo -e "  \033[0;33mtest\033[0m            запускает все тесты проекта"

	@echo ""
	@echo -e "Проверьте \033[0;33mMakefile\033[0m, чтобы понимать, что какая команда делает конкретно."


.PHONY: run
run:
	@if [ -z $(POETRY) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	@if [ $(mode) = dev ]; then $(ENV_VARS_PREFIX) $(POETRY) run uvicorn --factory src.app.main:get_application --reload --reload-delay 1; exit 0; fi
	@if [ $(mode) = prod ]; then $(ENV_VARS_PREFIX) $(POETRY) run uvicorn --factory src.app.main:get_application; exit 0; fi
	@echo -e "\033[0;33mнеизвестный режим запуска: $(mode)\033[0m"
	$(ENV_VARS_PREFIX) $(POETRY) run uvicorn --factory src.app.main:get_application --reload --reload-delay 1


.PHONY: install
install:
	@if [ -z $(POETRY) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	@if [ $(mode) = dev || $(mode) = test]; then $(POETRY) install; exit 0; fi
	@if [ $(mode) = prod ]; then $(POETRY) install --without dev,local-tools; exit 0; fi
	@echo -e "\033[0;33mнеизвестный режим запуска: $(mode)\033[0m"
	@echo -e "\033[0;33mполная установка.\033[0m"
	$(POETRY) install


.PHONY: shell
shell:
	@if [ -z $(POETRY) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	$(ENV_VARS_PREFIX) $(POETRY) run ipython --no-confirm-exit --no-banner --quick \
	--InteractiveShellApp.extensions="autoreload" \
	--InteractiveShellApp.exec_lines="%autoreload 2" \
	--InteractiveShellApp.exec_lines="import sys, pathlib, os" \
	--InteractiveShellApp.exec_lines="sys.path.insert(0, (pathlib.Path(os.getcwd()) / 'src').as_posix())" \
	--InteractiveShellApp.exec_lines="from app.core.models import tables" \
	--InteractiveShellApp.exec_lines="from app.api.v1.dependencies.databases import get_session" \
	--InteractiveShellApp.exec_files="scripts/ipython_shell_enter_message.py"

.PHONY: clean
clean:
	find . -type d -name "__pycache__" | xargs rm -rf {};
	rm -rf ./logs/*

.PHONY: lint
lint:
	@if [ -z $(POETRY) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	$(POETRY) run pyright $(NAME)
	$(POETRY) run isort --settings-path ./pyproject.toml --check-only $(NAME)
	$(POETRY) run black --config ./pyproject.toml --check $(NAME) --diff
	$(POETRY) run ruff check $(NAME)
	$(POETRY) run vulture $(NAME) --min-confidence 100
	$(POETRY) run bandit --configfile ./pyproject.toml -r ./$(NAME)/app

.PHONY: format
format:
	@if [ -z $(POETRY) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	$(POETRY) run isort --settings-path ./pyproject.toml $(NAME)
	$(POETRY) run black --config ./pyproject.toml $(NAME)

.PHONY: test
test:
	@if [ -z $(POETRY) ]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	$(ENV_VARS_PREFIX) $(POETRY) run pytest ./tests --cov-report xml --cov-fail-under 60 --cov ./$(NAME) -v
