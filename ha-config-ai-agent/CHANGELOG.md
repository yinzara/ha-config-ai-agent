# Changelog

All notable changes to the AI Configuration Agent add-on will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-26

### Initial Version

Initial version of the AI Configuration Agent add-on

## [0.1.1] - 2025-10-26

Enhanced API and UI to use streaming responses to provide
faster feedback to the frontend as queries are processed involving
tools.

Added tool call results (and tool calls) into the chat history UI.

## [0.1.2] - 2025-10-26

Refactored API to use websockets as streaming responses was
not working properly.

## [0.1.3] - 2025-10-27

Moved system prompt into configuration options and improved prompt.

## [0.1.4] - 2025-10-27

Moved system prompt into config file as full system prompt in options was breaking HA.

## [0.1.5] - 2025-10-28

General bug fixes and improvements.

## [0.1.6] - 2025-10-28

Add prompt caching support for models that support it (currently only Gemini and Claude)

## [0.1.7] - 2025-10-28

Prevent leaking secrets to LLMs