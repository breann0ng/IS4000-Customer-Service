"""Tests for RM escalation intake helpers."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from apps.api.chat.rm_intake import (
    RMIntakeAnswers,
    RMIntakeExtraction,
    RMIntakeState,
    _fallback_extract_answers,
    get_active_rm_intake,
    maybe_handle_rm_intake,
)


class RMIntakeTests(IsolatedAsyncioTestCase):
    """Cover the RM escalation intake flow across chat turns."""

    async def test_starts_intake_when_message_requires_escalation(self) -> None:
        """A fresh escalation should ask the RM prep questions."""
        result = await maybe_handle_rm_intake(
            session_messages=[],
            current_user_message="What should I invest in right now?",
            conversation_history=[
                {"role": "user", "content": "What should I invest in right now?"}
            ],
        )

        self.assertIsNotNone(result)
        if result is None:
            self.fail("Expected RM intake flow to start")
        self.assertIn("When would you like your RM to contact you?", result.response)
        self.assertIn(
            "What are the top 3 things you want to get out of the meeting?",
            result.response,
        )
        self.assertEqual(result.context["rm_intake"]["status"], "collecting")
        self.assertEqual(
            result.context["rm_intake"]["missing_fields"],
            ["preferred_contact_time", "meeting_format", "agenda", "top_outcomes"],
        )

    async def test_starts_intake_for_rm_review_scheduling(self) -> None:
        """RM review scheduling should also route into the intake flow."""
        result = await maybe_handle_rm_intake(
            session_messages=[],
            current_user_message="I want to schedule a review with my RM.",
            conversation_history=[
                {"role": "user", "content": "I want to schedule a review with my RM."}
            ],
        )

        self.assertIsNotNone(result)
        if result is None:
            self.fail("Expected RM intake flow to start")
        self.assertIn("When would you like your RM to contact you?", result.response)
        self.assertEqual(result.context["rm_intake"]["status"], "collecting")

    async def test_starts_intake_for_more_rm_booking_phrases(self) -> None:
        """Common RM booking phrases should all trigger the intake flow."""
        test_messages = [
            "Please book a meeting with my RM.",
            "Can you arrange a review with my RM?",
            "Set up a call with my relationship manager.",
        ]

        for message in test_messages:
            result = await maybe_handle_rm_intake(
                session_messages=[],
                current_user_message=message,
                conversation_history=[{"role": "user", "content": message}],
            )

            self.assertIsNotNone(result, msg=message)
            if result is None:
                self.fail(f"Expected RM intake flow to start for: {message}")
            self.assertIn("When would you like your RM to contact you?", result.response)
            self.assertEqual(result.context["rm_intake"]["status"], "collecting")

    async def test_partial_reply_keeps_collecting_missing_answers(self) -> None:
        """A partial intake reply should only ask for the remaining details."""
        active_state = RMIntakeState(
            trigger_message="I want advice on rebalancing my portfolio.",
            started_at="2026-04-09T12:00:00+00:00",
            last_updated_at="2026-04-09T12:00:00+00:00",
            collected_answers=RMIntakeAnswers(),
            missing_fields=["preferred_contact_time", "meeting_format", "agenda", "top_outcomes"],
        )
        session_messages = [
            SimpleNamespace(
                role="assistant",
                context={"rm_intake": active_state.model_dump()},
            )
        ]

        with patch(
            "apps.api.chat.rm_intake._extract_answers",
            new=AsyncMock(
                return_value=RMIntakeExtraction(
                    preferred_contact_time="Tomorrow afternoon",
                    meeting_format="online",
                )
            ),
        ):
            result = await maybe_handle_rm_intake(
                session_messages=session_messages,
                current_user_message="Tomorrow afternoon works and online is fine.",
                conversation_history=[
                    {"role": "assistant", "content": "Please share a few details for your RM."},
                    {"role": "user", "content": "Tomorrow afternoon works and online is fine."},
                ],
            )

        self.assertIsNotNone(result)
        if result is None:
            self.fail("Expected RM intake flow to continue")
        self.assertEqual(result.context["rm_intake"]["status"], "collecting")
        self.assertEqual(
            result.context["rm_intake"]["collected_answers"]["meeting_format"],
            "online",
        )
        self.assertEqual(
            result.context["rm_intake"]["missing_fields"],
            ["agenda", "top_outcomes"],
        )
        self.assertIn("What agenda should your RM prepare for?", result.response)
        self.assertIn("top 3 things you want to get out of the meeting", result.response)

    async def test_completed_reply_returns_rm_summary(self) -> None:
        """A full intake reply should complete the handoff and attach the summary."""
        active_state = RMIntakeState(
            trigger_message="I lost a lot of money and need to speak to someone senior.",
            started_at="2026-04-09T12:00:00+00:00",
            last_updated_at="2026-04-09T12:00:00+00:00",
            collected_answers=RMIntakeAnswers(),
            missing_fields=["preferred_contact_time", "meeting_format", "agenda", "top_outcomes"],
        )
        session_messages = [
            SimpleNamespace(
                role="assistant",
                context={"rm_intake": active_state.model_dump()},
            )
        ]

        with (
            patch(
                "apps.api.chat.rm_intake._extract_answers",
                new=AsyncMock(
                    return_value=RMIntakeExtraction(
                        preferred_contact_time="Friday morning",
                        meeting_format="in-person",
                        agenda="Review the recent portfolio losses and next steps",
                        top_outcomes=[
                            "Understand what drove the losses",
                            "Review risk adjustments",
                            "Agree on a recovery plan",
                        ],
                    )
                ),
            ),
            patch(
                "apps.api.chat.rm_intake._build_rm_summary",
                new=AsyncMock(
                    return_value=(
                        "Client prefers an in-person meeting on Friday morning to review recent "
                        "portfolio losses, understand the main drivers, discuss risk adjustments, "
                        "and agree on next steps."
                    )
                ),
            ),
        ):
            result = await maybe_handle_rm_intake(
                session_messages=session_messages,
                current_user_message=(
                    "Friday morning in person. Agenda: review losses. "
                    "Goals: understand drivers, adjust risk, plan next steps."
                ),
                conversation_history=[
                    {
                        "role": "user",
                        "content": "I lost a lot of money and need to speak to someone senior.",
                    },
                    {"role": "assistant", "content": "Please share a few details for your RM."},
                    {
                        "role": "user",
                        "content": (
                            "Friday morning in person. Agenda: review losses. "
                            "Goals: understand drivers, adjust risk, plan next steps."
                        ),
                    },
                ],
            )

        self.assertIsNotNone(result)
        if result is None:
            self.fail("Expected RM intake flow to complete")
        self.assertEqual(result.context["rm_intake"]["status"], "completed")
        self.assertEqual(
            result.context["rm_intake"]["summary"],
            result.response.split("\n", 3)[-1],
        )
        self.assertIn("### RM Handoff Summary", result.response)

    def test_fallback_extracts_numbered_reply(self) -> None:
        """The heuristic extractor should handle the numbered reply format."""
        extracted = _fallback_extract_answers(
            "\n".join(
                [
                    "1. Preferred contact time: Tomorrow after 3pm",
                    "2. Meeting format: Online",
                    "3. Agenda: Review portfolio rebalancing after the recent drawdown",
                    "4. Top 3 outcomes:",
                    "- Understand what changed in the portfolio",
                    "- Discuss suitable allocation adjustments",
                    "- Confirm the next steps",
                ]
            )
        )

        self.assertEqual(extracted.preferred_contact_time, "Tomorrow after 3pm")
        self.assertEqual(extracted.meeting_format, "online")
        self.assertEqual(
            extracted.agenda,
            "Review portfolio rebalancing after the recent drawdown",
        )
        self.assertEqual(
            extracted.top_outcomes,
            [
                "Understand what changed in the portfolio",
                "Discuss suitable allocation adjustments",
                "Confirm the next steps",
            ],
        )

    def test_get_active_rm_intake_ignores_completed_state(self) -> None:
        """Only a collecting RM intake should be treated as active."""
        completed_state = RMIntakeState(
            trigger_message="Please escalate this.",
            started_at="2026-04-09T12:00:00+00:00",
            last_updated_at="2026-04-09T12:05:00+00:00",
            collected_answers=RMIntakeAnswers(
                preferred_contact_time="Tomorrow morning",
                meeting_format="online",
                agenda="Discuss portfolio review",
                top_outcomes=["Understand performance", "Review options", "Agree next steps"],
            ),
            missing_fields=[],
            status="completed",
            summary="Client wants a portfolio review.",
        )

        active = get_active_rm_intake(
            [SimpleNamespace(role="assistant", context={"rm_intake": completed_state.model_dump()})]
        )

        self.assertIsNone(active)
