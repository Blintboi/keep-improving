"""Optional USB transport through the existing authenticated loopback control API.

Only the existing connection-code ciphertext crosses the USB boundary. The cloud
cooldown and quotas are neither consumed nor reset by a local transfer.
"""
def export(app,data):
    from .statistics_cloud import seal
    if not app.settings.statistics_sync_enabled or not app.settings.statistics_sync_group:raise ValueError('Connect the devices first.')
    app.tracker.flush();app.focus.flush()
    if hasattr(app,'wellbeing'):app.wellbeing.flush()
    snapshot=app.statistics_data.snapshot(app.settings.statistics_sync_group,app.settings.statistics_device_name)
    return dict(device=snapshot['device'],revision=str(snapshot['revision']),payload=seal(snapshot,app.settings.statistics_sync_group))

def receive(app,data):
    from .statistics_cloud import unseal
    if not app.settings.statistics_sync_enabled or not app.settings.statistics_sync_group:raise ValueError('Connect the devices first.')
    if set(data)!={'entry'}:raise ValueError('Invalid local transfer.')
    snapshot=unseal(data['entry'],app.settings.statistics_sync_group)
    changed=app.statistics_data.ingest(snapshot,app.settings.statistics_sync_group)
    if snapshot.get('remote_commands') or snapshot.get('preferences') or snapshot.get('scoped_rules',{}).get('records'):
        app._preferences_pending=True;app.apply_synchronized_preferences()
    return dict(imported=changed)
