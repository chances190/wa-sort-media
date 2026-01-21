"""Terminal UI using braille-style progress bars (no fallback nonsense).

Multi-category progress display with braille fill characters for Docker-like UX.
"""

from __future__ import annotations


class BrailleMultiProgress:
    """Docker compose style progress display."""

    _FILLS = [" ", "⡀", "⡄", "⡆", "⡇", "⣇", "⣧", "⣷", "⣿"]

    def __init__(self, title: str = "Organizing...", width: int = 24) -> None:
        self.title = title
        self.width = width
        self.totals: dict[str, int] = {}
        self.counts: dict[str, int] = {}
        self._lines_printed = 0

    def start(self, totals: dict[str, int]) -> None:
        # initialize
        self.totals = {k: int(v) for k, v in totals.items() if v}
        self.counts = {k: 0 for k in self.totals}
        # print header + one line per category
        print(f"{self.title}")
        for k, tot in self.totals.items():
            bar = self._render_bar(0)
            print(f" {k:12} {bar}  0/{tot}")
        # blank line separator
        print()
        # overall line
        total_all = sum(self.totals.values())
        bar = self._render_bar(0)
        print(f" {'Total':12} {bar}  0/{total_all}")
        self._lines_printed = len(self.totals) + 2  # categories + blank + total line (not header)

    def _render_bar(self, fraction: float) -> str:
        if fraction <= 0:
            return "[" + (" " * self.width) + "]"
        if fraction >= 1:
            return "[" + (self._FILLS[-1] * self.width) + "]"
        total_cells = self.width
        full = int(fraction * total_cells)
        part_frac = (fraction * total_cells) - full
        part_index = int(part_frac * (len(self._FILLS) - 1))
        bar = self._FILLS[-1] * full
        if full < total_cells:
            bar += self._FILLS[part_index]
            bar += " " * (total_cells - full - 1)
        return "[" + bar + "]"

    def _redraw(self) -> None:
        # move cursor up to the start of the block, overwrite lines
        if self._lines_printed == 0:
            return
        print(f"\x1b[{self._lines_printed}A", end="")
        # redraw category lines
        for k, tot in self.totals.items():
            cur = self.counts.get(k, 0)
            frac = cur / tot if tot else 0
            bar = self._render_bar(frac)
            print(f" {k:12} {bar}  {cur}/{tot}\x1b[K")
        # blank line separator
        print()
        # redraw total
        total_all = sum(self.totals.values())
        cur_all = sum(self.counts.values())
        frac_all = cur_all / total_all if total_all else 0
        bar = self._render_bar(frac_all)
        print(f" {'Total':12} {bar}  {cur_all}/{total_all}\x1b[K")

    def update(
        self,
        category: str,
        processed: int,
    ) -> None:
        if category not in self.totals:
            # ignore categories we didn't start with
            return
        self.counts[category] = processed
        self._redraw()

    def finish(self) -> None:
        # final redraw to ensure 100%
        for k in self.totals:
            self.counts[k] = self.totals[k]
        self._redraw()
        print()
