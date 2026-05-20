PKG_NAME        := cluster
PKG_VERSION     ?= $(shell git describe --tags --always --dirty 2>/dev/null || uv run python -c "import toml; print(\"v%s\" % (toml.load('pyproject.toml')['project']['version']))")
PKG_VERSION     ?= v0.1.0
PKG_MAINTAINER  := "RyanZ <ryanzzzz@foxmail.com>"
PKG_DESCRIPTION := "MQTT 节点管理与游戏控制系统（征服/占领/爆破三模式）"
PKG_URL         := "https://github.com/RyanZhangK/Cluster"

ROOT_DIR        := $(shell pwd)
SRC_DIR         := $(ROOT_DIR)/controller/src
BUILD_DIR       := $(ROOT_DIR)/build
DIST_DIR        := $(BUILD_DIR)/dist
STAGE_DIR       := $(BUILD_DIR)/stage
PKG_DIR         := $(BUILD_DIR)/pkg
NUITKA_OUT      := $(DIST_DIR)/main.dist

ARCH_NAME       := $(shell uname -m)
DEB_ARCH        := $(if $(filter x86_64,$(ARCH_NAME)),amd64,arm64)
PAC_ARCH        := $(ARCH_NAME)

INSTALL_BIN     := /usr/local/bin/$(PKG_NAME)
INSTALL_SHARE   := /usr/local/share/$(PKG_NAME)
INSTALL_DESKTOP := /usr/local/share/applications/$(PKG_NAME).desktop

export PATH     := $(shell ruby -e 'puts Gem.user_dir' 2>/dev/null)/bin:$(PATH)

.PHONY: all dev lint hot clean compile stage deb pacman bump
all: clean compile stage deb pacman 

dev:
	uv run controller

lint:
	uvx ruff check . && uvx ruff format --check .

hot:
	CLUSTER_GAME__UI_HOT_RELOAD=true uv run controller

clean: 
	@echo "==> 清理旧产物..."
	rm -rf $(BUILD_DIR)

compile:
	@echo "==> Nuitka 编译开始..."
	@mkdir -p $(DIST_DIR)
	uv sync --locked
	cd $(SRC_DIR) && uv run python -m nuitka \
		--enable-plugin=pyside6 \
		--standalone \
		--static-libpython=yes \
		--include-package=amqtt \
		--include-data-dir=../resources/audio=resources/audio \
		--output-dir=$(DIST_DIR) \
		--output-filename=$(PKG_NAME) \
		--assume-yes-for-downloads \
		--main=main.py

stage: 
	@echo "==> 组装 Stage 目录..."
	@rm -rf $(STAGE_DIR)
	
	install -dm755 $(STAGE_DIR)$(INSTALL_SHARE)/lib
	install -dm755 $(STAGE_DIR)$(INSTALL_SHARE)/audio
	install -dm755 $(STAGE_DIR)$(dir $(INSTALL_DESKTOP))
	install -dm755 $(STAGE_DIR)/usr/local/bin
	
	cp -r $(NUITKA_OUT)/* $(STAGE_DIR)$(INSTALL_SHARE)/lib/
	rm -f $(STAGE_DIR)$(INSTALL_SHARE)/lib/$(PKG_NAME)
	install -m755 $(NUITKA_OUT)/$(PKG_NAME) $(STAGE_DIR)$(INSTALL_SHARE)/lib/$(PKG_NAME)
	
	cp $(NUITKA_OUT)/resources/audio/*.wav $(STAGE_DIR)$(INSTALL_SHARE)/audio/ 2>/dev/null || true
	
	@echo ''
	@echo 'SHARE=$(INSTALL_SHARE)' >> $(STAGE_DIR)$(INSTALL_BIN)
	@echo 'exec env LD_LIBRARY_PATH="$$SHARE/lib:$$LD_LIBRARY_PATH" "$$SHARE/lib/$(PKG_NAME)" "$$@"' >> $(STAGE_DIR)$(INSTALL_BIN)
	@chmod 755 $(STAGE_DIR)$(INSTALL_BIN)
	
	@echo "[Desktop Entry]" > $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Name=Cluster" >> $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Comment=$(PKG_DESCRIPTION)" >> $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Exec=bash -c \"$(INSTALL_BIN) &\"" >> $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Icon=$(PKG_NAME)" >> $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Terminal=false" >> $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Type=Application" >> $(STAGE_DIR)$(INSTALL_DESKTOP)
	@echo "Categories=Utility;" >> $(STAGE_DIR)$(INSTALL_DESKTOP)

FPM_OPTS := -s dir -C $(STAGE_DIR) -n $(PKG_NAME) -v $(PKG_VERSION) \
            --maintainer $(PKG_MAINTAINER) --description $(PKG_DESCRIPTION) \
            --url $(PKG_URL) --prefix /

deb: 
	@echo "==> 构建 DEB 包..."
	@mkdir -p $(PKG_DIR)
	fpm $(FPM_OPTS) -t deb \
		--depends libgl1 --depends libegl1 --depends libasound2 \
		--depends libxcb-cursor0 --depends libxcb-icccm4 \
		--depends libxcb-image0 --depends libxcb-keysyms1 \
		--depends libxcb-randr0 --depends libxcb-render-util0 \
		--depends libxcb-shape0 --depends libxcb-shm0 \
		--depends libxcb-sync1 --depends libxcb-xfixes0 \
		--depends libxcb-xkb1 --depends libxcb-util1 \
		--depends libxkbcommon0 --depends libxkbcommon-x11-0 \
		--deb-no-default-config-files \
		-p $(PKG_DIR)/$(PKG_NAME)_$(PKG_VERSION)_$(DEB_ARCH).deb .

pacman: 
	@echo "==> 构建 Pacman 包..."
	@mkdir -p $(PKG_DIR)
	fpm $(FPM_OPTS) -t pacman \
		--depends qt6-base --depends alsa-lib \
		-p $(PKG_DIR)/$(PKG_NAME)-$(PKG_VERSION)-1-$(PAC_ARCH).pkg.tar.zst .

bump:
	uvx bump-my-version bump patch
