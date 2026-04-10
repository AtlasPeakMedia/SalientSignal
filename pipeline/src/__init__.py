"""SalientSignal data pipeline.

Modules:
    outlets       Outlet classification database loader and lookups.
    classifier    Audience classification (Algorithm 1).
    gdelt_client  GDELT DOC 2.0 query wrapper.
    baselines     30-day rolling baseline calculation (Algorithm 2).
    deviation     Daily deviation + z-score + level mapping (Algorithm 2).
    themes        GDELT theme tag extraction.
    coordination  Cross-country coordination detection (Algorithm 6).
    db            Supabase client wrapper.
    pipeline      Main orchestration loop.
"""

__version__ = "0.1.0"
