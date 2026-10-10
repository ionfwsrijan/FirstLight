# FirstLight — one-command workflows (cross-platform; works with GNU make).
PY ?= python
STACK ?= firstlight-shipit
REGION ?= ap-south-2
ENV ?= dev

.PHONY: install layer gate lint type test cov check sam-build deploy smoke clean

install:            ## install runtime + dev dependencies
	$(PY) -m pip install -e ".[dev]"

layer:              ## build the Lambda core layer + refresh the served console
	$(PY) sam/build_layer.py

gate: install       ## run the full test suite (the commit gate)
	$(PY) -m firstlight.cli gate

lint:               ## ruff
	$(PY) -m ruff check .

type:               ## mypy
	$(PY) -m mypy firstlight

cov:                ## tests + coverage floor
	$(PY) -m pytest --cov=firstlight --cov-report=term-missing

test: gate

check: lint type layer          ## everything CI runs before deploy
	$(PY) sam/build_layer.py --check
	cfn-lint sam/template.yaml
	sam validate -t sam/template.yaml

sam-build: layer
	sam build --template sam/template.yaml

deploy: sam-build                ## deploy/refresh the Ship It twin
	sam deploy --template .aws-sam/build/template.yaml --stack-name $(STACK) \
		--capabilities CAPABILITY_IAM --no-confirm-changeset --resolve-s3 \
		--parameter-overrides Env=$(ENV) --region $(REGION)

smoke:              ## hit the deployed /health and console
	curl -sS "$$(sam list stack-outputs --stack-name $(STACK) --region $(REGION) --output json | $(PY) -c 'import sys,json;print(next(o["OutputValue"] for o in json.load(sys.stdin) if o["OutputKey"]=="ApiUrl"))')health"

clean:
	rm -rf .aws-sam sam/build-layer .pytest_cache .mypy_cache .ruff_cache
