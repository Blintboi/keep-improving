"""One user-facing renewal time, retaining migrated counters and their usage."""
from dataclasses import replace
from datetime import datetime


def normalize(settings):
    # Retain old ledger identities so BudgetPeriods carries consumed time and
    # delivered markers to the global boundary instead of re-seeding a budget.
    resets={key:settings.budget_reset_minute for key in settings.budget_reset_overrides}
    return replace(settings,budget_reset_overrides=resets) if resets!=settings.budget_reset_overrides else settings


def carry_markers(store,previous,updated,wall=None):
    changed=[key for key,minute in previous.budget_reset_overrides.items()
             if minute!=updated.budget_reset_overrides.get(key,updated.budget_reset_minute)]
    if not changed: return
    from .budget_periods import BudgetPeriods
    ledger=BudgetPeriods(store); wall=wall or datetime.now().astimezone()
    with store.db:
        for key in changed:
            ledger._carry_markers(key,ledger.day(wall,previous.budget_reset_overrides[key]),
                                  ledger.day(wall,updated.budget_reset_minute))


def migrate(store,wall=None):
    settings=store.settings(); updated=normalize(settings)
    if updated is not settings:
        carry_markers(store,settings,updated,wall); store.save_settings(updated)
    return updated
