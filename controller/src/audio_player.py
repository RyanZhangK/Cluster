import logging
from collections import deque
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect

from .config import AUDIO_DIR, AUDIO_FILES

logger = logging.getLogger(__name__)


class AudioPlayer(QObject):
    """
    串行播放队列：同一时刻只播放一条音效，后续请求排队等候。
    延迟加载：第一次播放时才创建 QSoundEffect，避免启动阻塞。
    继承 QObject 以支持 sender() 和 Slot。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._effects: dict[str, QSoundEffect] = {}
        self._queue: deque[str] = deque()
        self._current: QSoundEffect | None = None
        self._method_cache = {}

    def __getattr__(self, name: str) -> Any:
        if name in self._method_cache:
            return self._method_cache[name]
        if name.startswith("play_"):
            action = name[len("play_") :]

            def wrapper(*args):
                key = f"{action}_{args[0]}" if args else action
                self._play(key)

            self._method_cache[name] = wrapper
            return wrapper
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    # ── 加载 ──────────────────────────────────────────────

    def _get_or_load(self, key: str) -> QSoundEffect | None:
        if key in self._effects:
            return self._effects[key]
        if key not in AUDIO_FILES:
            logger.warning(f"音效 {key} 未在 AUDIO_FILES 中定义")
            return None
        filepath = Path(AUDIO_DIR) / AUDIO_FILES[key]
        if not filepath.exists():
            logger.warning(f"音效文件不存在: {filepath}，{key} 将被跳过")
            return None
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(filepath)))
        # 用 lambda 捕获 effect 引用，避免依赖 sender()
        effect.playingChanged.connect(lambda e=effect: self._on_playing_changed(e))
        self._effects[key] = effect
        logger.info(f"已加载音效: {key} <- {filepath}")
        return effect

    # ── 队列调度 ──────────────────────────────────────────

    def _play(self, key: str) -> None:
        self._queue.append(key)
        if self._current is None:
            self._play_next()

    def _play_next(self) -> None:
        while self._queue:
            key = self._queue.popleft()
            effect = self._get_or_load(key)
            if effect is None:
                continue
            self._current = effect
            # 若文件尚未加载完毕，等 statusChanged 再播
            if effect.status() == QSoundEffect.Status.Ready:
                effect.play()
            else:
                effect.statusChanged.connect(lambda e=effect: self._on_status_ready(e))
            return
        self._current = None

    def _on_status_ready(self, effect: QSoundEffect) -> None:
        if effect is self._current and effect.status() == QSoundEffect.Status.Ready:
            effect.statusChanged.disconnect()
            effect.play()

    def _on_playing_changed(self, effect: QSoundEffect) -> None:
        if effect is self._current and not effect.isPlaying():
            self._current = None
            self._play_next()
