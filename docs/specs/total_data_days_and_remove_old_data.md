# Remove old data
It's simple. Garmin data > 30 days must be removed from the DB at the sync. In example if today is day 31 of the month, data from day 1 must be removed from the database.

# Sync process
At sync, if database is empty data retrieved must be from the previous 30 days. In example, if today is day 31 of the month, data retrieved must be from the 1 until de 30.

## Sync when database it is not empty
- If database is not empty the sync only will retrieve data from the very last day in the database until the current day.

## Data retrieved
- Data retrieved from garmin regarding activities must be ALL the available. Common and advanced metrics like vertical oscilation, ground contact time, step length...

# Documentation
- Document all the specification functionaly and technical on the folder `docs/implementations` at the end.

# Testing
- Unit test are a MUST. Implement test for this implementation and check that all the test pass.

# Before implementation
Think carefully about the implementation and let the markdown with it on `docs\specs` folder
 - Model to plan: `Opus 4.7`

# Implementation
 - Model to implement: `Sonnet 4.6`