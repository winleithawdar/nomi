from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.checkins.semantics import (
    LABEL_AS_USUAL,
    LABEL_CHANGED_FROM_USUAL,
    LABEL_NEEDS_YOU_NOW,
    STEP_AS_USUAL,
    STEP_CHANGED,
    STEP_NEEDS_YOU,
    assess_session,
)


class SessionSemanticsTest(unittest.TestCase):
    def test_worked_example_tired_and_slow_is_changed_from_usual(self) -> None:
        result = assess_session(
            latency_minutes=85,
            median_latency=25,
            wellbeing=3,
            median_wellbeing=4,
            session_text="3 a bit tired today ok",
        )
        self.assertEqual(result.label, LABEL_CHANGED_FROM_USUAL)
        self.assertEqual(result.rhythm_level, 1)
        self.assertEqual(result.self_report_level, 1)
        self.assertEqual(result.language_level, 1)
        self.assertEqual(result.suggested_step, STEP_CHANGED)
        self.assertEqual(max(result.rhythm_level, result.self_report_level, result.language_level), 1)
        self.assertIn("tired", result.lexicon_hits)
        self.assertTrue(result.reasons)
        self.assertIsNone(result.tfidf_similarity)

    def test_help_and_fell_is_needs_you_now_even_if_fast_and_well(self) -> None:
        result = assess_session(
            latency_minutes=5,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="please help I fell",
        )
        self.assertEqual(result.label, LABEL_NEEDS_YOU_NOW)
        self.assertEqual(result.rhythm_level, 0)
        self.assertEqual(result.self_report_level, 0)
        self.assertEqual(result.language_level, 2)
        self.assertEqual(result.suggested_step, STEP_NEEDS_YOU)
        self.assertIn("help", result.lexicon_hits)
        self.assertIn("fell", result.lexicon_hits)

    def test_label_is_max_of_tracks_not_average(self) -> None:
        result = assess_session(
            latency_minutes=5,
            median_latency=25,
            wellbeing=5,
            median_wellbeing=4,
            session_text="please help",
        )
        self.assertEqual(result.rhythm_level, 0)
        self.assertEqual(result.self_report_level, 0)
        self.assertEqual(result.language_level, 2)
        self.assertEqual(result.label, LABEL_NEEDS_YOU_NOW)

    def test_missed_sets_rhythm_2(self) -> None:
        result = assess_session(
            latency_minutes=None,
            median_latency=25,
            wellbeing=None,
            median_wellbeing=4,
            session_text="",
            missed=True,
        )
        self.assertEqual(result.rhythm_level, 2)
        self.assertEqual(result.label, LABEL_NEEDS_YOU_NOW)
        self.assertEqual(result.suggested_step, STEP_NEEDS_YOU)

    def test_rhythm_stays_0_when_faster_than_double_median(self) -> None:
        result = assess_session(
            latency_minutes=40,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="ok",
        )
        self.assertEqual(result.rhythm_level, 0)
        self.assertEqual(result.label, LABEL_AS_USUAL)

    def test_rhythm_1_at_exactly_double_median(self) -> None:
        result = assess_session(
            latency_minutes=50,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="fine",
        )
        self.assertEqual(result.rhythm_level, 1)
        self.assertEqual(result.label, LABEL_CHANGED_FROM_USUAL)

    def test_rhythm_0_when_median_missing(self) -> None:
        result = assess_session(
            latency_minutes=90,
            median_latency=None,
            wellbeing=4,
            median_wellbeing=4,
            session_text="ok",
        )
        self.assertEqual(result.rhythm_level, 0)

    def test_self_report_2_for_wellbeing_1_and_2(self) -> None:
        for score in (1, 2, 1.0, 2.0):
            result = assess_session(
                latency_minutes=10,
                median_latency=25,
                wellbeing=score,
                median_wellbeing=4,
                session_text="ok",
            )
            self.assertEqual(result.self_report_level, 2, msg=score)
            self.assertEqual(result.label, LABEL_NEEDS_YOU_NOW)

    def test_self_report_1_when_three_vs_usual_four(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=3,
            median_wellbeing=4,
            session_text="ok",
        )
        self.assertEqual(result.self_report_level, 1)
        self.assertEqual(result.label, LABEL_CHANGED_FROM_USUAL)

    def test_self_report_0_when_three_and_median_below_four(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=3,
            median_wellbeing=3,
            session_text="ok",
        )
        self.assertEqual(result.self_report_level, 0)

    def test_self_report_0_when_wellbeing_missing(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=None,
            median_wellbeing=4,
            session_text="ok",
        )
        self.assertEqual(result.self_report_level, 0)
        self.assertEqual(result.label, LABEL_AS_USUAL)

    def test_usual_phrases_do_not_override_help(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=5,
            median_wellbeing=4,
            session_text="I am fine but please help",
        )
        self.assertEqual(result.language_level, 2)
        self.assertEqual(result.label, LABEL_NEEDS_YOU_NOW)
        self.assertIn("help", result.lexicon_hits)

    def test_usual_phrases_only_reason_when_language_0(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="ok fine I ate and slept alright",
        )
        self.assertEqual(result.language_level, 0)
        self.assertEqual(result.label, LABEL_AS_USUAL)
        self.assertEqual(result.suggested_step, STEP_AS_USUAL)
        self.assertTrue(any("ok" in hit or hit == "fine" for hit in result.lexicon_hits) or result.reasons)

    def test_level2_lexicon_phrases(self) -> None:
        phrases = (
            "help",
            "hurt",
            "pain",
            "fall",
            "fell",
            "scared",
            "cannot",
            "can't",
            "not ok",
            "not okay",
            "dizzy",
            "chest",
        )
        for phrase in phrases:
            result = assess_session(
                latency_minutes=10,
                median_latency=25,
                wellbeing=4,
                median_wellbeing=4,
                session_text=f"today {phrase} really",
            )
            self.assertEqual(result.language_level, 2, msg=phrase)
            self.assertEqual(result.label, LABEL_NEEDS_YOU_NOW, msg=phrase)

    def test_level1_lexicon_phrases(self) -> None:
        phrases = (
            "lonely",
            "tired",
            "cannot sleep",
            "no appetite",
            "worried",
            "worse",
        )
        for phrase in phrases:
            text = phrase
            if phrase == "cannot sleep":
                # "cannot" is a level-2 cue; this case is covered as needs-you.
                # Use the remaining drift cue to assert level 1.
                continue
            result = assess_session(
                latency_minutes=10,
                median_latency=25,
                wellbeing=4,
                median_wellbeing=4,
                session_text=f"a bit {text} today",
            )
            self.assertEqual(result.language_level, 1, msg=phrase)
            self.assertEqual(result.label, LABEL_CHANGED_FROM_USUAL, msg=phrase)

    def test_cannot_sleep_is_at_least_language_2_because_cannot(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="I cannot sleep",
        )
        self.assertEqual(result.language_level, 2)
        self.assertIn("cannot", result.lexicon_hits)

    def test_tfidf_skipped_with_fewer_than_two_priors(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="ok today",
            prior_session_texts=["ok fine I ate"],
        )
        self.assertIsNone(result.tfidf_similarity)
        self.assertEqual(result.language_level, 0)

    def test_tfidf_shift_is_language_1_never_2(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="quantum pineapple bicycle volcano",
            prior_session_texts=[
                "ok fine I ate lunch and slept well today",
                "good morning I ate breakfast and slept alright",
            ],
        )
        self.assertIsNotNone(result.tfidf_similarity)
        assert result.tfidf_similarity is not None
        self.assertLess(result.tfidf_similarity, 0.35)
        self.assertEqual(result.language_level, 1)
        self.assertEqual(result.label, LABEL_CHANGED_FROM_USUAL)

    def test_tfidf_similar_wording_stays_language_0(self) -> None:
        result = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="ok fine I ate lunch and slept well today",
            prior_session_texts=[
                "ok fine I ate lunch and slept well today",
                "ok fine I ate breakfast and slept well today",
            ],
        )
        self.assertIsNotNone(result.tfidf_similarity)
        assert result.tfidf_similarity is not None
        self.assertGreaterEqual(result.tfidf_similarity, 0.35)
        self.assertEqual(result.language_level, 0)
        self.assertEqual(result.label, LABEL_AS_USUAL)

    def test_reasons_only_include_fired_rules(self) -> None:
        quiet = assess_session(
            latency_minutes=10,
            median_latency=25,
            wellbeing=4,
            median_wellbeing=4,
            session_text="hello there",
        )
        self.assertEqual(quiet.rhythm_level, 0)
        self.assertEqual(quiet.self_report_level, 0)
        self.assertEqual(quiet.language_level, 0)
        self.assertEqual(quiet.label, LABEL_AS_USUAL)
        fired = assess_session(
            latency_minutes=80,
            median_latency=25,
            wellbeing=1,
            median_wellbeing=4,
            session_text="help",
        )
        self.assertGreater(len(fired.reasons), len(quiet.reasons))
        self.assertTrue(any("help" in reason.lower() or "contained" in reason.lower() for reason in fired.reasons))


if __name__ == "__main__":
    unittest.main()
