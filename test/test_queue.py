"""Regression tests for DropOldestQueue — the GUI event queue that
silently drops the oldest item at capacity instead of blocking or
raising queue.Full.

Run either way:
    py test/test_queue.py
    py -m pytest test/test_queue.py
"""

# Copyright 2026 Costel Iordan (costel.iordan@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import importlib.util
import queue
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "plan_console", HERE.parent / "plan-console.py")
pc = importlib.util.module_from_spec(_spec)
sys.modules["plan_console"] = pc
_spec.loader.exec_module(pc)


# ----------------------------------------------------------- basic behaviour
def test_put_below_capacity_keeps_all():
    q = pc.DropOldestQueue(maxsize=3)
    q.put("a")
    q.put("b")
    q.put("c")
    assert q.qsize() == 3
    assert q.get_nowait() == "a"
    assert q.get_nowait() == "b"
    assert q.get_nowait() == "c"


def test_put_at_capacity_drops_oldest():
    q = pc.DropOldestQueue(maxsize=2)
    q.put("a")
    q.put("b")
    q.put("c")                       # over capacity — "a" is dropped
    assert q.qsize() == 2
    assert q.get_nowait() == "b"
    assert q.get_nowait() == "c"


def test_put_never_blocks_or_raises_full():
    q = pc.DropOldestQueue(maxsize=1)
    for i in range(1000):
        q.put(i)                     # must never block or raise queue.Full
    assert q.qsize() == 1
    assert q.get_nowait() == 999


def test_put_nowait_is_a_method():
    # regression: put_nowait was accidentally de-indented to a free
    # function, so self.put_nowait raised AttributeError at runtime.
    q = pc.DropOldestQueue(maxsize=2)
    assert callable(q.put_nowait)
    q.put_nowait("x")
    assert q.get_nowait() == "x"


# ----------------------------------------------------- task-ticket accounting
def test_dropped_item_releases_task_ticket():
    # When the oldest item is dropped to make room, its unfinished_tasks
    # ticket must be released so queue.join() eventually completes.
    q = pc.DropOldestQueue(maxsize=1)
    q.put("a")
    q.put("b")                       # drops "a" — its ticket is released
    # one task remains ("b"); mark it done and join must not hang
    q.get_nowait()
    q.task_done()
    q.join()                         # would hang forever if "a"'s ticket leaked


def test_task_tickets_stay_consistent_under_churn():
    q = pc.DropOldestQueue(maxsize=2)
    for i in range(5):
        q.put(i)                     # drops 0, 1, 2 — only 3, 4 remain
    assert q.qsize() == 2
    while not q.empty():
        q.get_nowait()
        q.task_done()
    q.join()                         # must not hang


# ------------------------------------------------------------- maxsize <= 0
def test_unbounded_queue_never_drops():
    q = pc.DropOldestQueue(maxsize=0)           # 0 means unbounded
    for i in range(50):
        q.put(i)
    assert q.qsize() == 50


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
