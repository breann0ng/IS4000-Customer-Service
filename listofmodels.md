# Available Google Gemini Models (March 2026)

This document lists the valid model identifiers for the Google Gemini API as of March 20, 2026. These IDs are verified via the `genai.list_models()` method.

## Gemini 3 Series (Flagship - 2026)

- `gemini-3.1-flash-lite-preview`: Lowest latency, high-volume cost-efficient model.
- `gemini-3-flash-preview`: Stable 3.0 generation Flash model.

## Gemini 2.5 Series (Stable Production)

- `gemini-2.5-flash-lite`: Cost-optimized for massive scale.

## Usage Note

Always use the exact identifier string (e.g., `gemini-3.1-flash-lite-preview`) in your `.env` file. If a model returns 404, it may be because the `-preview` suffix is required.
