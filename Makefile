aism-init:
	bash ./scripts/ai-skills/init.bash

aism-re-init:
	rm -rf .ai-skill-manager
	bash scripts/ai-skills/init.bash

aism-sync:
	bash scripts/ai-skills/sync.bash