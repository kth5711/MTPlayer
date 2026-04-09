from i18n import tr

from .dock import refresh_bookmark_dock
from .selection import selected_category_names, selected_direct_bookmark_ids, selected_file_nodes
from .shared import DEFAULT_CATEGORY, normalize_category, status
from .state import refresh_bookmark_marks


def delete_selected_bookmarks(main):
    selected_ids = _selected_bookmark_ids_for_removal(main)
    selected_categories = set(selected_category_names(main))
    blocked_default = DEFAULT_CATEGORY in selected_categories
    selected_categories.discard(DEFAULT_CATEGORY)
    if not selected_ids and not selected_categories and not blocked_default:
        return
    removed = _remove_selected_bookmarks(main, selected_ids)
    moved_to_default, removed_categories = _remove_selected_categories(main, selected_categories)
    _refresh_bookmark_deletion(main)
    if removed > 0 or removed_categories > 0 or moved_to_default > 0:
        _save_bookmark_state(main)
        status(main, tr(main, "북마크삭제: {parts}", parts=", ".join(_deletion_parts(main, removed, moved_to_default, removed_categories))))
        return
    if blocked_default:
        status(main, tr(main, "미분류는 삭제할 수 없습니다."))


def _selected_bookmark_ids_for_removal(main) -> set[str]:
    selected_ids = set(selected_direct_bookmark_ids(main))
    selected_files = list(selected_file_nodes(main))
    for path, category in selected_files:
        for entry in getattr(main, "bookmarks", []) or []:
            if str(entry.get("path", "")) == path and normalize_category(entry.get("category", DEFAULT_CATEGORY)) == category:
                bookmark_id = str(entry.get("id", ""))
                if bookmark_id:
                    selected_ids.add(bookmark_id)
    return selected_ids


def _remove_selected_bookmarks(main, selected_ids: set[str]) -> int:
    before = len(getattr(main, "bookmarks", []) or [])
    main.bookmarks = [entry for entry in getattr(main, "bookmarks", []) or [] if str(entry.get("id", "")) not in selected_ids]
    return max(0, before - len(main.bookmarks))


def _remove_selected_categories(main, selected_categories: set[str]) -> tuple[int, int]:
    if not selected_categories:
        return 0, 0
    moved_to_default = 0
    for entry in getattr(main, "bookmarks", []) or []:
        category = normalize_category(entry.get("category", DEFAULT_CATEGORY))
        if category not in selected_categories or category == DEFAULT_CATEGORY:
            continue
        entry["category"] = DEFAULT_CATEGORY
        moved_to_default += 1
    kept_categories, removed_categories = _kept_categories(main, selected_categories)
    main.bookmark_categories = kept_categories
    return moved_to_default, removed_categories


def _kept_categories(main, selected_categories: set[str]) -> tuple[list[str], int]:
    kept: list[str] = []
    seen: set[str] = set()
    removed = 0
    for name in getattr(main, "bookmark_categories", []) or []:
        category = normalize_category(name)
        if category in seen:
            continue
        seen.add(category)
        if category in selected_categories:
            removed += 1
            continue
        kept.append(category)
    return kept, removed


def _refresh_bookmark_deletion(main):
    refresh_bookmark_dock(main, keep_selection=False)
    refresh_bookmark_marks(main)


def _save_bookmark_state(main):
    try:
        main.save_config()
    except Exception:
        pass


def _deletion_parts(main, removed: int, moved_to_default: int, removed_categories: int) -> list[str]:
    parts: list[str] = []
    if removed > 0:
        parts.append(tr(main, "북마크 {count}개", count=removed))
    if moved_to_default > 0:
        parts.append(tr(main, "미분류 이동 {count}개", count=moved_to_default))
    if removed_categories > 0:
        parts.append(tr(main, "카테고리 {count}개", count=removed_categories))
    return parts
