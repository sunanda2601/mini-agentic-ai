# Rollback Strategy

## Purpose

The platform uses explicit versioning for agents, tools, prompts, and the application so that a previously validated version can be restored if a new version causes failures or unsafe behavior.

## Version Tracking

The current versions are maintained in:

`app/version.py`

The workflow trace records:

- Application version
- Agent versions
- Tool versions

This allows each workflow execution to be associated with the versions that produced it.

## Rollback Process

If a new version introduces a regression:

1. Identify the failing workflow or evaluation.
2. Review the workflow trace to identify the versions used.
3. Restore the last known-good application, agent, tool, or prompt version.
4. Run the unit and tool contract tests.
5. Run the safety evaluation suite.
6. Promote the previous version only after all required tests pass.
7. Re-run the affected workflow to verify recovery.

## Safety Gate

A rollback candidate must pass:

- Unit tests
- Tool contract tests
- Safety evaluations
- End-to-end workflow validation

Unsafe or unverified versions must not be promoted.

## Current Baseline

The current prototype baseline is:

- Application: `1.0.0`
- Agents: `1.0.0`
- Tools: `1.0.0`
- Prompts: `1.0.0`

This baseline can be used as the known-good version for the prototype.

## Rollback Principle

The platform follows a simple rule:

> If a new version fails validation, return to the last validated version rather than continuing with the failing version.