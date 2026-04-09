"""Tests for RM contact follow-up helpers."""

from unittest import TestCase

from apps.api.chat.followups import RM_FOLLOW_UP_PROMPT, apply_rm_follow_up


class ChatFollowUpTests(TestCase):
    """Cover the RM follow-up prompt insertion logic."""

    def test_appends_follow_up_for_rm_contact_question(self) -> None:
        """A user asking how to contact the RM should get the extra prompt."""
        response, suggestions = apply_rm_follow_up(
            "How do I contact my RM?",
            "You can contact your Relationship Manager through secure message.",
        )

        self.assertIn(RM_FOLLOW_UP_PROMPT, response)
        self.assertEqual(suggestions, [RM_FOLLOW_UP_PROMPT])

    def test_appends_follow_up_for_rm_contact_response(self) -> None:
        """A response that mentions direct RM contact should get the extra prompt."""
        response, suggestions = apply_rm_follow_up(
            "I want to know my options.",
            "You can reach your Relationship Manager directly through our secure message channel.",
        )

        self.assertIn(RM_FOLLOW_UP_PROMPT, response)
        self.assertEqual(suggestions, [RM_FOLLOW_UP_PROMPT])

    def test_does_not_duplicate_existing_follow_up(self) -> None:
        """If the assistant already asked the follow-up, do not add it again."""
        response, suggestions = apply_rm_follow_up(
            "How do I contact my RM?",
            f"You can contact your RM directly.\n\n{RM_FOLLOW_UP_PROMPT}",
            [RM_FOLLOW_UP_PROMPT],
        )

        self.assertEqual(response.count(RM_FOLLOW_UP_PROMPT), 1)
        self.assertEqual(suggestions, [RM_FOLLOW_UP_PROMPT])
