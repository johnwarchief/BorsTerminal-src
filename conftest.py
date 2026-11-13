"""Root pytest conftest for the BorsTerminal worktree.

Makes the worktree root importable so that tests can do
``from tools.phase497.separation import paths, build_shared`` even though
``tools/`` is a namespace package (no ``__init__.py``).

Added for Task 1 (technical data-layer separation) per controller Ruling 2.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))