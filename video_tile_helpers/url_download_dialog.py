from __future__ import annotations

import os
from typing import Optional

from PyQt6 import QtWidgets

from i18n import tr
from .url_download_languages import (
    DEFAULT_URL_SUBTITLE_LANGUAGE,
    URL_SUBTITLE_LANGUAGES,
    normalize_url_subtitle_language,
)
from url_media_resolver import media_source_display_name


HEIGHT_OPTIONS = (
    (0, "원본"),
    (2160, "2160p"),
    (1440, "1440p"),
    (1080, "1080p"),
    (720, "720p"),
    (480, "480p"),
    (360, "360p"),
    (240, "240p"),
)


def ask_url_save_options(tile, source: str) -> Optional[dict]:
    defaults = _load_url_save_defaults(tile)
    dialog = _build_url_save_dialog(tile, source, defaults)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    save_dir = _validate_url_save_dir(tile, dialog, dialog._edt_dir.text())
    if not save_dir:
        return None
    return {
        "save_dir": save_dir,
        "audio_only": bool(dialog._chk_audio_only.isChecked()),
        "height": int(dialog._cmb_height.currentData() or 0),
        "download_subtitles": bool(dialog._chk_subtitles.isChecked()),
        "subtitle_language": str(dialog._cmb_sub_lang.currentData() or DEFAULT_URL_SUBTITLE_LANGUAGE).strip()
        or DEFAULT_URL_SUBTITLE_LANGUAGE,
    }


def remember_url_save_options(tile, options: dict) -> None:
    main = tile._main_window()
    if main is None:
        return
    config = getattr(main, "config", None)
    if not isinstance(config, dict):
        return
    save_dir = str(options.get("save_dir") or "").strip()
    if save_dir:
        config["url_save_dir"] = save_dir
        config["last_dir"] = save_dir
        if hasattr(main, "last_dir"):
            main.last_dir = save_dir
    config["url_save_audio_only"] = bool(options.get("audio_only", False))
    config["url_save_height"] = int(options.get("height", 0) or 0)
    config["url_save_subtitles"] = bool(options.get("download_subtitles", True))
    subtitle_language = normalize_url_subtitle_language(str(options.get("subtitle_language") or ""))
    config["url_save_sub_lang"] = subtitle_language
    config["url_save_sub_langs"] = subtitle_language


def _load_url_save_defaults(tile) -> dict:
    main = tile._main_window()
    config = getattr(main, "config", {}) if main is not None else {}
    return {
        "save_dir": (
            str(config.get("url_save_dir", "") or "").strip()
            or str(config.get("last_dir", "") or "").strip()
            or os.path.expanduser("~")
        ),
        "audio_only": bool(config.get("url_save_audio_only", False)),
        "height": int(config.get("url_save_height", 0) or 0),
        "download_subtitles": bool(config.get("url_save_subtitles", True)),
        "subtitle_language": normalize_url_subtitle_language(
            str(
                config.get("url_save_sub_lang", "")
                or config.get("url_save_sub_langs", "")
                or DEFAULT_URL_SUBTITLE_LANGUAGE
            )
        ),
    }


def _build_url_save_dialog(tile, source: str, defaults: dict):
    dialog = QtWidgets.QDialog(tile)
    dialog.setWindowTitle(tr(tile, "URL 저장 옵션"))
    dialog.resize(560, 0)
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    layout.addWidget(_make_source_label(tile, source, dialog))
    layout.addLayout(_build_form_layout(tile, dialog, defaults))

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
        | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        parent=dialog,
    )
    layout.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    _wire_dialog_callbacks(dialog, defaults)
    _update_url_save_option_widgets(dialog)
    return dialog


def _make_source_label(tile, source: str, parent):
    label = QtWidgets.QLabel(
        tr(
            tile,
            "대상: {name}\n{url}",
            name=media_source_display_name(source) or tr(tile, "URL 미디어"),
            url=source,
        ),
        parent,
    )
    label.setWordWrap(True)
    return label


def _build_form_layout(tile, dialog, defaults: dict):
    form = QtWidgets.QFormLayout()
    form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.addRow(tr(tile, "저장 위치:"), _build_dir_row(tile, dialog, defaults))
    dialog._chk_audio_only = QtWidgets.QCheckBox(tr(tile, "오디오만 저장"), dialog)
    dialog._chk_audio_only.setChecked(bool(defaults.get("audio_only", False)))
    form.addRow("", dialog._chk_audio_only)
    dialog._cmb_height = _build_height_combo(dialog, defaults)
    form.addRow(tr(tile, "저장 사전설정:"), dialog._cmb_height)
    dialog._chk_subtitles = QtWidgets.QCheckBox(tr(tile, "자막도 함께 저장"), dialog)
    dialog._chk_subtitles.setChecked(bool(defaults.get("download_subtitles", True)))
    form.addRow("", dialog._chk_subtitles)
    dialog._cmb_sub_lang = _build_subtitle_language_combo(dialog, defaults)
    form.addRow(tr(tile, "자막 언어:"), dialog._cmb_sub_lang)
    return form


def _build_dir_row(tile, dialog, defaults: dict):
    row = QtWidgets.QHBoxLayout()
    dialog._edt_dir = QtWidgets.QLineEdit(str(defaults.get("save_dir") or ""), dialog)
    dialog._btn_browse = QtWidgets.QPushButton(tr(tile, "변경..."), dialog)
    row.addWidget(dialog._edt_dir, 1)
    row.addWidget(dialog._btn_browse)
    return row


def _build_height_combo(dialog, defaults: dict):
    combo = QtWidgets.QComboBox(dialog)
    selected_index = 0
    for index, (value, label) in enumerate(HEIGHT_OPTIONS):
        combo.addItem(label, value)
        if int(value) == int(defaults.get("height", 0) or 0):
            selected_index = index
    combo.setCurrentIndex(selected_index)
    return combo


def _build_subtitle_language_combo(dialog, defaults: dict):
    combo = QtWidgets.QComboBox(dialog)
    combo.setMaxVisibleItems(18)
    selected_index = 0
    selected_subtitle_language = str(defaults.get("subtitle_language") or DEFAULT_URL_SUBTITLE_LANGUAGE)
    for index, (code, label) in enumerate(URL_SUBTITLE_LANGUAGES):
        combo.addItem(label, code)
        if code == selected_subtitle_language:
            selected_index = index
    combo.setCurrentIndex(selected_index)
    return combo


def _wire_dialog_callbacks(dialog, defaults: dict) -> None:
    dialog._chk_audio_only.toggled.connect(lambda _checked=False: _update_url_save_option_widgets(dialog))
    dialog._chk_subtitles.toggled.connect(lambda _checked=False: _update_url_save_option_widgets(dialog))
    dialog._btn_browse.clicked.connect(
        lambda: dialog._edt_dir.setText(
            _pick_url_save_folder(
                dialog,
                str(dialog._edt_dir.text() or "").strip() or str(defaults.get("save_dir") or ""),
            )
            or str(dialog._edt_dir.text() or "").strip()
        )
    )


def _update_url_save_option_widgets(dialog) -> None:
    dialog._cmb_height.setEnabled(not bool(dialog._chk_audio_only.isChecked()))
    dialog._cmb_sub_lang.setEnabled(bool(dialog._chk_subtitles.isChecked()))


def _pick_url_save_folder(parent, start_dir: str) -> str:
    return str(
        QtWidgets.QFileDialog.getExistingDirectory(
            parent,
            tr(parent, "저장 폴더 선택"),
            str(start_dir or "").strip() or os.path.expanduser("~"),
        )
        or ""
    ).strip()


def _validate_url_save_dir(tile, parent, save_dir: str) -> Optional[str]:
    save_dir = str(save_dir or "").strip()
    if not save_dir:
        QtWidgets.QMessageBox.warning(parent, tr(tile, "URL 저장"), tr(tile, "저장 위치를 지정하세요."))
        return None
    try:
        os.makedirs(save_dir, exist_ok=True)
    except Exception as exc:
        QtWidgets.QMessageBox.critical(
            parent,
            tr(tile, "URL 저장"),
            tr(tile, "저장 폴더를 만들 수 없습니다.\n\n{error}", error=exc),
        )
        return None
    return save_dir
