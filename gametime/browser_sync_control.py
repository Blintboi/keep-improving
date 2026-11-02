"""Browser UI for the existing desktop account worker; sessions stay on disk."""
from dataclasses import replace
from .statistics_sync import group_code,display_code
from .statistics_cloud import new_code


class SyncControl:
    def __init__(self,control): self.control=control; self.app=control.app; self.result={}; self.generated=set()

    def state(self):
        app=self.app; session=app.account_session
        return dict(enabled=app.settings.statistics_sync_enabled,name=app.settings.statistics_device_name,
                    signed_in=bool(session),account_name=session.get('name','') if session else '',busy=app._auth_busy,
                    syncing=app._sync_busy,status=str(app.statistics_sync_status()),result=self.result,
                    computers=app.statistics_data.devices(app.settings.statistics_sync_group))

    def reveal(self,data): return dict(code=display_code(self.app.settings.statistics_sync_group))

    def generate(self,data):
        code=new_code(); self.generated.add(code)
        return dict(code=display_code(code))

    def command(self,data):
        action=data.get('action'); app=self.app
        if action=='sync': app.request_statistics_sync(); return self.state()
        if action not in ('login','logout','revoke'): raise ValueError('Invalid request.')
        if action=='revoke' and data.get('confirmed') is not True: raise ValueError('Confirm revoking the connection code.')
        if app._auth_busy: raise ValueError('The application is busy. Try again.')
        self.result={}
        def finished(value,warning): self.result={'ok':bool(value.get('ok')),'error':str(app.t(warning)) if warning else ''}
        if not app.request_account(action,'',finished): raise ValueError('The application is busy. Try again.')
        return self.state()

    def save(self,data):
        app=self.app; enabled=data.get('enabled'); code=group_code(data.get('code','')); name=data.get('name','')
        settings=replace(app.settings,statistics_sync_enabled=enabled,statistics_sync_group=code,statistics_device_name=name).validate()
        if app.settings_have_draft(): raise ValueError('Save or discard the open desktop settings draft before changing settings here.')
        if app._auth_busy: raise ValueError('The application is busy. Try again.')
        def commit():
            previous=app.settings.statistics_sync_group
            current=replace(app.settings,statistics_sync_enabled=enabled,statistics_sync_group=code,statistics_device_name=name)
            self.control.save(current); app.store.pending_connection(clear=True)
            app.statistics_sync.cancel(); app._sync_busy=False; app._sync_startup_pending=False
            app._sync_event_pending=False; app.statistics_event_timer.stop()
            app._sync_status='Sync enabled.' if enabled else 'Statistics sync is off.'; app._sync_success_at=''
            if previous!=code: app.statistics.reset_computer_filters()
            app.request_statistics_sync(); app.update_statistics_sync_status()
            self.result={'ok':True,'error':''}
        self.result={}
        if enabled and app.account_session:
            app.store.pending_connection(code)
            def finished(value,warning):
                if value.get('ok'):
                    try: commit()
                    except (OSError,ValueError): self.result={'ok':False,'error':str(app.t('Could not save connection settings. Try again.'))}
                else: self.result={'ok':False,'error':str(app.t(warning)),'other_group':value.get('error')=='other_group'}
            if not app.request_account('rotate' if data.get('replace_confirmed') is True else 'activate',code,finished):
                raise ValueError('The application is busy. Try again.')
        elif enabled and code in self.generated: raise ValueError('Sign in with GitHub before activating a new connection code.')
        else: commit()
        return self.state()

    def rename(self,data):
        self.app.statistics_data.set_device_alias(self.app.settings.statistics_sync_group,data['id'],data['name'])
        return True
