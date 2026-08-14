"""Migration command placeholder owned by the CLI boundary."""

from __future__ import annotations


def main() -> int:
    """Report that persistence migrations begin in Phase 2."""
    print("No persistence migrations configured yet; database work starts in Phase 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
