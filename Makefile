CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -std=c11
BIN_DIR := bin
C_BIN := $(BIN_DIR)/modular-detect
VERSION ?= $(shell cat VERSION 2>/dev/null | tr -d '[:space:]')
ifeq ($(VERSION),)
VERSION := 0.0.0
endif

.PHONY: all c go clean test

all: c go

c: $(C_BIN)

$(C_BIN): hardware/modular-detect.c
	@mkdir -p $(BIN_DIR)
	$(CC) $(CFLAGS) -o $@ $<

go:
	cd cmd/modular && go build -ldflags "-X main.version=$(VERSION)" \
		-o ../../bin/modular .

test: c
	./$(C_BIN) | python3 -c "import json,sys; json.load(sys.stdin); print('modular-detect: valid JSON')"

clean:
	rm -rf $(BIN_DIR)
