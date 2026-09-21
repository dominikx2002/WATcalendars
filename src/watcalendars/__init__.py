"""WATcalendars - turns WAT faculty schedule pages into .ics calendars.

Layout:

    core/       contracts and orchestration (models, registry, pipeline)
    fetch/      getting bytes off the internet (http, browser, downloads)
    parsers/    turning those bytes into lessons - one module per faculty
    store/      writing results (ics, groups, employees)
    faculties/  one FacultySpec per faculty; the only place they differ
    cli.py      the single entry point (`watcal`)

Paths live in core.paths, not here; import them from there.
"""

__version__ = "0.4.0"
