"""Compatibility entry point: all time limits live in Settings now."""
def game_limits_dialog(app,gid=None):
    return app.open_budget({'kind':'game','value':gid} if isinstance(gid,str) else None)
