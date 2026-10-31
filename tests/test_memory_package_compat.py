from __future__ import annotations

import sys

import fram_serving.memory as memory


def test_memory_package_registers_and_reexports_legacy_module() -> None:
    legacy_name = "fram_serving._memory_legacy"

    assert legacy_name in sys.modules
    assert memory.CognitiveMemoryStore is sys.modules[legacy_name].CognitiveMemoryStore
    assert memory.MemoryWriteError is sys.modules[legacy_name].MemoryWriteError
    assert memory.WorkingMemoryStore is sys.modules[legacy_name].WorkingMemoryStore
    assert memory.uuid is sys.modules[legacy_name].uuid
