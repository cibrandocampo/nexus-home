# Garage firmware commands. Each one runs in the toolchain image (docker/Dockerfile): the host only needs
# Docker, make and git. The project is bind-mounted at /work and the container runs as you, so build/
# and dist/ stay yours.
IMAGE   := nexus-garage-toolchain
RUN     := docker run --rm -u $(shell id -u):$(shell id -g) -v "$(CURDIR):/work" -w /work
FQBN    := arduino:renesas_uno:unor4wifi
port    ?= /dev/ttyACM0
version ?=

.PHONY: help image test build ota upload update smoke shell

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

image: ## Build the toolchain image (the other targets do it; CI builds it first and sets IMAGE_BUILT=1)
	@test -n "$(IMAGE_BUILT)" || docker build -q -t $(IMAGE) docker/ >/dev/null

test: image ## Host tests (g++)
	$(RUN) $(IMAGE) test/run.sh

build: image ## Host tests + compile -> dist/garage-<version>.bin (version= overrides FW_VERSION)
	$(RUN) $(IMAGE) tools/build.sh $(version)

ota: image ## dist/garage-<version>.bin -> .ota (version= required)
	@test -n "$(version)" || { echo "usage: make ota version=x.y.z" >&2; exit 2; }
	$(RUN) $(IMAGE) python3 -I tools/make_ota.py dist/garage-$(version).bin dist/garage-$(version).ota

upload: image ## Compile and flash over USB (port=/dev/ttyACM0, flags=-D… for test builds): the bench board only
	@test -e $(port) || { echo "$(port) not found: is the board plugged in?" >&2; exit 2; }
	$(RUN) --device $(port) --group-add $$(stat -c %g $(port)) $(IMAGE) \
	  sh -c 'arduino-cli compile --fqbn $(FQBN) $(if $(flags),--build-property "compiler.cpp.extra_flags=$(flags)") \
	           --output-dir build/upload firmware >/dev/null && \
	         arduino-cli upload --fqbn $(FQBN) -p $(port) --input-dir build/upload firmware; s=$$?; \
	         rm -rf build/upload; exit $$s'

update: image ## Network update (ip= required, version= optional); token from GARAGE_TOKEN or asked for
	@test -n "$(ip)" || { echo "usage: make update ip=<controller-ip> [version=x.y.z]" >&2; exit 2; }
	$(RUN) -it --network host -e GARAGE_TOKEN -e OTA_PORT $(IMAGE) tools/update.sh $(ip) $(version)

smoke: image ## Read-only checks against a running board (ip= required; token from GARAGE_TOKEN)
	@test -n "$(ip)" || { echo "usage: make smoke ip=<controller-ip>" >&2; exit 2; }
	$(RUN) --network host -e GARAGE_TOKEN $(IMAGE) sh -c 'test/api_smoke.sh $(ip) "$$GARAGE_TOKEN"'

shell: image ## A shell in the toolchain image
	$(RUN) -it $(IMAGE) bash
