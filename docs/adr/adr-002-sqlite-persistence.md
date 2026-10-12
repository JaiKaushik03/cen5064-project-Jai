# ADR 002: SQLite Persistence

**Date:** 2026-10-10
**Status:** accepted

## Context

A maintenance request must remain visible after PropertyCare restarts. The professor and peer reviewer need to run a clean clone without configuring a database server. The current slice stores a small number of requests for a local course demonstration.

## Decision

Use SQLite through Python's standard-library `sqlite3` module. Only `MaintenanceRequestRepository` executes SQL. It creates the database directory and table automatically, saves with parameterized statements, commits each insert, and closes every connection.

The default file is `data/propertycare.db`, resolved relative to `app.py`. An optional `PROPERTYCARE_DB_PATH` environment variable selects a different file for automated tests. Database files are local generated data and are excluded from Git.

## Consequences

Installation needs no database credentials, server, or migration command. Requests survive new repository connections and application restarts. Tests can use isolated database files without changing demonstration data. SQLite fits this local slice; substantial concurrent writes or a hosted multi-user deployment would require revisiting this choice. Removing the local database removes its requests, so it should be backed up when that data matters.
