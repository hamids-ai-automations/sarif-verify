.PHONY: test demo check docker clean

PYTHON ?= python

test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	-$(PYTHON) -m sarif_verify.demo

check:
	$(PYTHON) -m sarif_verify check --strict fixtures/good.sarif

docker:
	docker build -t sarif-verify .

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
