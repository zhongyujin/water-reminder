import tempfile
import unittest
from pathlib import Path
from timer_model import INTERVAL, SNOOZE, ReminderState, load, save, today

class TimerTests(unittest.TestCase):
    def test_reminder_is_due_at_exactly_thirty_minutes(self):
        s=ReminderState.fresh(1000)
        self.assertFalse(s.due(1000+INTERVAL-1))
        self.assertTrue(s.due(1000+INTERVAL))

    def test_confirm_starts_a_new_full_interval(self):
        s=ReminderState.fresh(1000)
        s.drank(3000)
        self.assertEqual(s.drinks,1)
        self.assertEqual(s.next_due,4800)
        self.assertTrue(s.enabled)

    def test_snooze_is_five_minutes(self):
        s=ReminderState.fresh(1000)
        s.snooze(2000)
        self.assertFalse(s.due(2000+SNOOZE-1))
        self.assertTrue(s.due(2000+SNOOZE))
        self.assertEqual(s.drinks,0)

    def test_pause_resume_preserves_remaining_time(self):
        s=ReminderState.fresh(1000)
        s.pause(1100)
        self.assertEqual(s.remaining,1700)
        self.assertFalse(s.due(100000))
        s.resume(100000)
        self.assertEqual(s.next_due,101700)
        self.assertTrue(s.enabled)

    def test_new_day_resets_count_without_changing_deadline(self):
        s=ReminderState.fresh(0)
        s.drinks=3
        due=s.next_due
        s.refresh_day(86400)
        self.assertEqual(s.drinks,0)
        self.assertEqual(s.day,today(86400))
        self.assertEqual(s.next_due,due)

    def test_saved_paused_timer_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json'
            state=ReminderState.fresh(1000)
            state.pause(1300)
            save(path,state)
            restored=load(path,1400)
            self.assertEqual(restored,state)
            self.assertEqual(list(Path(d).glob('*.tmp')),[])

    def test_invalid_preferences_recover_to_safe_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json'
            path.write_text('{broken',encoding='utf-8')
            state=load(path,1000)
            self.assertEqual(state.next_due,2800)
            self.assertEqual(state.drinks,0)

if __name__=='__main__':unittest.main(verbosity=2)
