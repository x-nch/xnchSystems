"""Search input widget with paste support."""

from __future__ import annotations

from textual.widgets import Input


class SearchInput(Input):
    """Input widget that handles paste and multi-line input."""

    def __init__(self, placeholder: str = "Search...", **kwargs) -> None:
        super().__init__(placeholder=placeholder, **kwargs)
