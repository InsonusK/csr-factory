repo-init:
	bash ./scripts/init.bash

skill-sync:
	bash ./scripts/ai-skills/sync.bash

test:
	pytest

lint:
	python -m compileall src tests
