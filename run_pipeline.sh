#!/bin/zsh
# run_pipeline.sh
# Runs the full email → LinkedIn posts pipeline.
# Scheduled Tue/Thu/Fri at 1 PM via cron.
#
# Script execution order is defined in pipeline.config.json
# Edit that file to add, remove, or reorder steps — do not hardcode scripts here.

PROJECT="/Users/josephugaldeberrocal/Documents/Zimplixio_Marketing"
PYTHON="$PROJECT/.venv/bin/python3"
LOG="$PROJECT/tmp/pipeline_run.log"

cd "$PROJECT" || exit 1
mkdir -p tmp

echo "----------------------------------------" >> "$LOG"
echo "Run started: $(date)" >> "$LOG"

$PYTHON - << 'PYEOF' >> "$LOG" 2>&1
import json, subprocess, sys, os

project = os.getcwd()
python  = os.path.join(project, '.venv', 'bin', 'python3')

with open('pipeline.config.json') as f:
    config = json.load(f)

for script in config['scripts']:
    print(f'[{script}]', flush=True)
    result = subprocess.run([python, script], capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end='', flush=True)
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr, flush=True)
    if result.returncode != 0:
        print(f'STOPPED: {script} exited with code {result.returncode}', flush=True)
        sys.exit(result.returncode)
PYEOF

STATUS=$?
echo "Run finished: $(date) — exit $STATUS" >> "$LOG"
