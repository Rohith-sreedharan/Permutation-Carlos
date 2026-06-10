#!/usr/bin/env bash
set -euo pipefail
cd /root/Permutation-Carlos/backend
source .venv/bin/activate

python3 /root/Permutation-Carlos/proof_batch_screenshots/phase13/generate_phase13_token_pool.py

OUT_PREFIX=/root/Permutation-Carlos/proof_batch_screenshots/phase13/load_50_beta_auth_endpoints_only_v2
set +e
TOKENS_PATH=/tmp/phase13_tokens.txt .venv/bin/locust \
  -f /root/Permutation-Carlos/proof_batch_screenshots/phase13/locust_phase13_50_endpoints.py \
  --host https://beta.beatvegas.app \
  --headless -u 50 -r 10 --run-time 60s \
  --csv=$OUT_PREFIX > ${OUT_PREFIX}.log 2>&1
LOCUST_EXIT=$?
set -e

echo LOCUST_EXIT=$LOCUST_EXIT
tail -n 140 ${OUT_PREFIX}.log
echo ---CSV_STATS---
tail -n 20 ${OUT_PREFIX}_stats.csv
