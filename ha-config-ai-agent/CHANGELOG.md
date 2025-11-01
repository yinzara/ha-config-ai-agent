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

## [0.1.8] - 2025-10-28

Import and export conversation history

## [0.1.9] - 2025-10-28

Added configurable temperature parameter for LLM calls. You can now specify the temperature (0.0-2.0) in the add-on configuration to control the randomness of the AI's responses. When not specified, the LLM provider's default temperature is used

## [0.1.10] - 2025-10-30

Made cache control configurable and added token usage tracking

## [0.1.11] - 2025-10-31

Enhanced search functionality to support file path patterns. When search_pattern starts with "/", it's treated as a glob pattern and only searches actual files (skipping virtual entities/devices/areas). Example: `/packages/*.yaml` will match all YAML files in the packages directory.