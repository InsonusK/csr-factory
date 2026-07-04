#!/bin/bash
echo "Initializing AI Skill Manager..."

git clone https://github.com/InsonusK/ai-skill-manager
mv ai-skill-manager .ai-skill-manager
cd .ai-skill-manager
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
echo "Initialization complete. AI Skill Manager is ready to use."