"""Timer rules and atomic storage for the desktop water reminder."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import time
import uuid

INTERVAL = 30 * 60
SNOOZE = 5 * 60
SHANGHAI = timezone(timedelta(hours=8))


def today(now):
    return datetime.fromtimestamp(now, SHANGHAI).strftime("%Y-%m-%d")


@dataclass
class ReminderState:
    enabled: bool
    next_due: float
    remaining: float
    day: str
    drinks: int = 0

    @classmethod
    def fresh(cls, now):
        return cls(True, now + INTERVAL, INTERVAL, today(now), 0)

    def refresh_day(self, now):
        if self.day != today(now):
            self.day = today(now)
            self.drinks = 0

    def due(self, now):
        return self.enabled and now >= self.next_due

    def seconds_left(self, now):
        return max(0, self.next_due - now) if self.enabled else self.remaining

    def pause(self, now):
        self.remaining = self.seconds_left(now)
        self.enabled = False

    def resume(self, now):
        if not self.enabled:
            self.next_due = now + max(1, self.remaining)
            self.enabled = True

    def drank(self, now):
        self.refresh_day(now)
        self.drinks += 1
        self.remaining = INTERVAL
        self.next_due = now + INTERVAL
        self.enabled = True

    def snooze(self, now):
        self.remaining = SNOOZE
        self.next_due = now + SNOOZE
        self.enabled = True


def load(path, now=None):
    now = time.time() if now is None else now
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        state = ReminderState(**data)
        if not isinstance(state.enabled, bool) or not isinstance(state.drinks, int):
            raise ValueError("Invalid reminder state")
        if state.remaining < 0 or state.drinks < 0:
            raise ValueError("Invalid timer value")
        state.refresh_day(now)
        return state
    except (OSError, ValueError, TypeError):
        return ReminderState.fresh(now)


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(asdict(data) if isinstance(data, ReminderState) else data,
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
