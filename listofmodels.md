# Available Google Gemini Models (March 2026)

This document lists the valid model identifiers for the Google Gemini API as of March 20, 2026. These IDs are verified via the `genai.list_models()` method.

## Gemini 3 Series (Flagship - 2026)
*   `gemini-3.1-pro-preview`: Advanced reasoning and agentic workflows.
*   `gemini-3.1-flash-lite-preview`: Lowest latency, high-volume cost-efficient model.
*   `gemini-3-pro-preview`: Stable 3.0 generation Pro model.
*   `gemini-3-flash-preview`: Stable 3.0 generation Flash model.
*   `gemini-3-pro-image-preview`: High-fidelity image generation and editing.
*   `gemini-3.1-flash-image-preview`: Fast, efficient image generation.

## Gemini 2.5 Series (Stable Production)
*   `gemini-2.5-pro`: High-intelligence, 1M+ context window.
*   `gemini-2.5-flash`: Fast, high-volume production model.
*   `gemini-2.5-flash-lite`: Cost-optimized for massive scale.
*   `gemini-2.5-flash-image`: Standard image generation.

## Gemini 2.0 Series (Legacy)
*   `gemini-2.0-flash`: Legacy 2.0 generation.
*   `gemini-2.0-flash-lite`: Legacy 2.0 lite version.

## Specialized Models
*   `deep-research-pro-preview-12-2025`: Agentic autonomous research model.
*   `gemini-2.5-computer-use-preview-10-2025`: Screen interaction and UI automation.
*   `gemini-robotics-er-1.5-preview`: Robotics and embodied reasoning.

## Usage Note
Always use the exact identifier string (e.g., `gemini-3.1-flash-lite-preview`) in your `.env` file. If a model returns 404, it may be because the `-preview` suffix is required.
