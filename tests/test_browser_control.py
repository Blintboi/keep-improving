"""Browser controls use isolated profiles and never launch real applications."""
from dataclasses import replace
from copy import deepcopy
import base64,json,threading,uuid
from unittest.mock import patch
import unittest
import test_qt_ui as fixture
from gametime.browser_control import BrowserControl
from gametime.notification_rules import builtin
from gametime.focus import FocusSettings


class BrowserControlTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump
    def setUp(self):
        fixture.QtInterfaceTests.setUp(self); self.control=BrowserControl(self.app)
    def request(self,action,data=None,revision=None,identity=None):
        return self.control.dispatch(dict(action=action,data=data or {},revision=revision or self.control.revision(),id=identity or uuid.uuid4().hex))
    def ok(self,action,data=None):
        result=self.request(action,data); self.assertTrue(result['ok'],result); return result['result']
    def budget(self):
        return dict(key='web-fixture',kind='group',name='Web fixture',members=[dict(kind='site',value='https://youtube.com/watch?v=fixture')],
                    seconds=1800,enabled=True,overlay=True,days=[0,2,4],usage=True,plan=None,appearance={})
    def test_state_redacts_credentials_and_read_does_not_start_focus(self):
        with self.store.db: self.store.db.execute("INSERT OR REPLACE INTO settings VALUES ('browser_pairing','fixture-secret')")
        with patch.object(self.app.focus,'start') as start:
            value=self.ok('state'); start.assert_not_called()
        raw=json.dumps(value); self.assertNotIn('fixture-secret',raw); self.assertNotIn('access_token',raw)
        self.assertEqual(len(value['games']),3); self.assertEqual(len(value['notifications']),4)
        self.assertTrue(value['icons']); self.assertTrue(value['triggers'])
    def test_budget_roundtrip_normalizes_domains_and_keeps_native_forms_current(self):
        self.ok('budget.save',self.budget())
        self.assertEqual(self.app.settings.wellbeing_rules[0]['members'],[dict(kind='site',value='youtube.com')])
        self.assertEqual(self.app.settings.budget_active_days['web-fixture'],[0,2,4]); self.assertFalse(self.app.settings_have_draft())
        self.ok('settings.save',{'budget_reset_minute':60})
        self.assertFalse(self.app.settings_have_draft()); self.assertEqual(self.app.global_day_start.time().hour(),1)
        self.ok('budget.delete',{'key':'web-fixture'}); self.assertFalse(self.app.settings.wellbeing_rules)
    def test_validation_is_atomic_and_private_settings_cannot_be_patched(self):
        before=deepcopy(self.app.settings)
        for data in ({'statistics_sync_group':'a'*32},{'budget_reset_minute':1440},{'language':'invalid'}):
            self.assertFalse(self.request('settings.save',data)['ok']); self.assertEqual(self.app.settings,before)
        item=self.budget();item['seconds']=-1
        self.assertFalse(self.request('budget.save',item)['ok']);self.assertEqual(self.app.settings,before)
    def test_stale_save_is_rejected_and_retry_does_not_repeat_action(self):
        stale=self.control.revision();self.ok('focus.save',{'work':31})
        result=self.request('focus.save',{'work':32},stale);self.assertTrue(result['conflict']);self.assertEqual(self.app.focus.settings.work,31)
        identity=uuid.uuid4().hex;revision=self.control.revision()
        with patch.object(self.app.focus,'start') as start:
            first=self.request('focus.start',revision=revision,identity=identity)
            self.assertEqual(first,self.request('focus.start',revision=revision,identity=identity));start.assert_called_once()
            self.assertFalse(self.request('focus.stop',revision=revision,identity=identity)['ok'])
    def test_zero_focus_and_pause_stop_share_desktop_timer(self):
        self.ok('focus.save',{'work':17,'short_break':0,'long_break':0,'rounds':0})
        self.ok('focus.start');self.assertTrue(self.app.focus.running);self.assertEqual(self.app.focus.remaining,1020)
        self.ok('focus.pause');self.assertFalse(self.app.focus.running)
        self.ok('focus.start');self.ok('focus.stop');self.assertFalse(self.app.focus.restricting)
    def test_builtin_notification_delete_recreate_and_custom_actions(self):
        item=builtin(self.app.settings,'warning');item.update(trigger='startup',timeout=0,icon='preset:focus',action=dict(kind='pomodoro',work=17,short_break=0,long_break=0,rounds=0))
        self.ok('notification.save',dict(key='builtin:warning',value=item))
        self.assertEqual(self.app.settings.notification_overrides['warning']['action']['work'],17)
        self.ok('notification.delete',dict(key='builtin:warning'))
        self.assertIsNone(builtin(self.app.settings,'warning'))
        self.ok('notification.save',dict(key='builtin:warning',value=item));self.assertIsNotNone(builtin(self.app.settings,'warning'))
    def test_native_unapplied_draft_survives_and_blocks_overwriting(self):
        self.app.games_path.setText(str(self.base/'Different'))
        self.assertFalse(self.request('settings.save',dict(budget_reset_minute=120))['ok'])
        self.assertEqual(self.app.games_path.text(),str(self.base/'Different'));self.assertEqual(self.app.settings.budget_reset_minute,0)
    def test_game_visibility_and_exclusion_survive_other_settings(self):
        gid=self.games[0].id
        self.ok('activity.change',dict(kind='game',key=gid,hidden=True,enabled=False))
        self.ok('settings.save',dict(language='en'))
        self.assertIn(gid,self.app.hidden_ids);self.assertFalse(self.app.catalog.enabled(self.games[0]))
        with patch.object(self.app,'play_game') as launch:
            self.ok('state');launch.assert_not_called();self.ok('game.launch',dict(id=gid));launch.assert_called_once_with(gid)
    def test_queued_http_work_runs_on_gui_thread(self):
        result=[]
        worker=threading.Thread(target=lambda:result.append(self.control.request({'action':'state'})))
        worker.start()
        while worker.is_alive(): self.pump(.02)
        worker.join();self.assertTrue(result[0]['ok']);self.assertEqual(self.control.pending,0)
    def test_full_path_application_exclusions_are_visible_and_reversible(self):
        path=r'C:\Fixture\editor.exe'
        self.ok('activity.add',dict(kind='app',value=path))
        self.ok('activity.change',dict(kind='app',key='editor.exe',enabled=False))
        activity=next(a for a in self.ok('state')['activities'] if a['member']['value']=='editor.exe')
        self.assertTrue(activity['excluded'])
        self.ok('activity.change',dict(kind='app',key='editor.exe',enabled=True))
        activity=next(a for a in self.ok('state')['activities'] if a['member']['value']=='editor.exe')
        self.assertFalse(activity['excluded'])
    def test_statistics_are_read_only_and_invalid_periods_are_rejected(self):
        result=self.ok('statistics');self.assertEqual(result['total'],0)
        self.assertFalse(self.request('statistics',dict(start='2020-01-01',end='2026-11-02'))['ok'])
        with patch.object(self.app.tracker,'flush') as flush:
            self.ok('statistics');flush.assert_not_called()

    def test_icon_upload_is_local_bounded_and_rejects_non_images(self):
        from pathlib import Path
        value=self.ok('icon.upload',dict(image=base64.b64encode(Path('gametime/browser_extension/icons/16.png').read_bytes()).decode()))
        path=Path(value['path']);self.assertEqual(path.parent,self.base/'notification-icons');self.assertTrue(path.is_file())
        for image in ('invalid',base64.b64encode(b'<html>not an image</html>').decode(),'a'*450001):
            self.assertFalse(self.request('icon.upload',dict(image=image))['ok'])
    def test_activity_add_manual_game_assignment_and_removal_are_explicit(self):
        self.ok('activity.add',dict(kind='site',value='https://chess.com/play'))
        self.assertTrue(any(a['member']['value']=='chess.com' for a in self.ok('state')['activities']))
        gid=self.ok('game.add',dict(path=str(self.exe),name='Manual fixture'))
        self.assertEqual(self.app.catalog.rules[str(self.exe).lower()],gid)
        from gametime.removal import RemovalPlan
        with patch('gametime.removal.plan_removal',return_value=RemovalPlan('Fixture','Fixture','uri','https://example.com')),patch('gametime.removal.execute') as execute:
            plan=self.ok('game.removal',dict(id=gid));execute.assert_not_called()
            self.assertFalse(self.request('game.removal',dict(id=gid,confirm='wrong'))['ok']);execute.assert_not_called()
            self.ok('game.removal',dict(id=gid,confirm=plan['confirm']));execute.assert_called_once()
    def test_notification_action_never_launches_during_read_or_preview_and_preserves_running_focus(self):
        rule=builtin(self.app.settings,'warning');rule.update(action=dict(kind='app',path=str(self.exe)))
        with patch('gametime.qt_notification_options.launch_application') as launch:
            self.ok('notification.preview',dict(value=rule));launch.assert_not_called()
            self.ok('notification.action',dict(action=rule['action']));launch.assert_called_once_with(str(self.exe))
        self.ok('focus.start');remaining=self.app.focus.remaining
        self.assertFalse(self.request('notification.action',dict(action=dict(kind='pomodoro',work=17,short_break=0,long_break=0,rounds=0)))['ok'])
        self.assertEqual(self.app.focus.remaining,remaining)
    def test_account_status_redacts_sessions_and_revoke_requires_explicit_confirmation(self):
        self.app.account_session={'name':'Fixture','access_token':'not-for-browser','refresh_token':'not-for-browser'}
        self.assertNotIn('not-for-browser',json.dumps(self.ok('sync.state')))
        with patch.object(self.app,'request_account',return_value=True) as request:
            self.assertFalse(self.request('sync.command',dict(action='revoke'))['ok']);request.assert_not_called()
            self.ok('sync.command',dict(action='revoke',confirmed=True));request.assert_called_once()
    def test_http_authentication_origin_host_and_oversized_body_guards(self):
        from gametime.browser_activity import BrowserBridge
        import urllib.request,urllib.error
        bridge=BrowserBridge(self.store,port=0,control=self.control.request)
        def call(headers,body=b'{"action":"live"}'):
            request=urllib.request.Request(f'http://127.0.0.1:{bridge.port}/control',data=body,headers=headers)
            try:
                with urllib.request.urlopen(request) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as error:return error.code,{}
        try:
            auth={'Authorization':'Bearer '+bridge.token,'Content-Type':'application/json'}
            self.assertEqual(call({})[0],401)
            self.assertEqual(call(dict(auth,Origin='https://example.com'))[0],403)
            self.assertEqual(call(dict(auth,Host='attacker.example'))[0],403)
            self.assertEqual(call(auth,b' '*524289)[0],400)
            results=[];worker=threading.Thread(target=lambda:results.append(call(dict(auth,Origin='chrome-extension://'+'a'*32))))
            worker.start()
            while worker.is_alive():self.pump(.02)
            worker.join();self.assertEqual(results[0][0],200);self.assertTrue(results[0][1]['ok'])
        finally:bridge.close()


if __name__=='__main__': unittest.main()
