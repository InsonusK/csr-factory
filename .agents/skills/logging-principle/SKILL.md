---
name: logging-principle
description: Describes logging rules for development
whenToUse: when writing code that requires logging or choosing a log level
tags:
  - logging
  - development
  - common-workflow
---

# Goal
- Standardize logging rules during development.

# Core Principle
- We classify errors and logs.
- Log messages must provide enough information to understand exactly what happened.

# Rule
## MUST
- Always add logging to code.
- Always provide a parameter that enables `debug` level logs. It MUST be disabled by default.
- Classify logs by level:
  - **Info**: logging key workflow milestones (e.g., "scan completed, found the following results") or important integration events (e.g., "message received", "database record created", "response sent").
  - **Warning**: errors that do not stop execution but deserve attention.
  - **Error**: business errors that are expected to interrupt program execution (e.g., "could not find files in the provided directory", "system X did not respond to the request", "system X rejected our request", "system X responded with a status code != 2xx").
  - **Critical**: exceptions that were caught.

## SHOULD NOT
- Use `print`, `write`, or similar plain output mechanisms instead of a proper logging framework.

# Anti-patterns
- **Using `print`, `write`, etc.**
  - Example: `print("scan completed")` | `Console.WriteLine("record created")`
  - Consequence: limited logging capabilities, and if a log aggregation system is added later, all logging code will have to be rewritten.
  - Instead: prefer the logging mechanisms provided by the language or framework (e.g., `logging`, `loguru`, `NLog`, `Serilog`, etc.).

- **Using abstract text in log messages**
  - Example: `task completed` | `record created`
  - Consequence: the log message does not clarify what actually happened.
  - Instead: include information that makes the context clear (e.g., `task 'clear db' completed` | `record 1234 created`).

# Check list
- [ ] Logging is added for all meaningful operations.
- [ ] There is a parameter to enable/disable `debug` logs and it is disabled by default.
- [ ] Logs are classified into Info / Warning / Error / Critical.
- [ ] Log messages contain specific information about the event.
- [ ] `print`, `write`, and similar constructs are not used for logging.
