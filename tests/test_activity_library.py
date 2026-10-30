"""Activity-owned appearance remains independent of shared budget accounting."""
from dataclasses import replace
from datetime import datetime,timedelta
from unittest.mock import patch,Mock
import unittest
import test_qt_ui as fixture
from gametime.model import Settings
from gametime.activities import activity_key,activity_settings,has_budget,known_activities
from gametime.wellbeing import target
from gametime.qt_budgets import new_rule
from gametime.qt_countdown_targets import CountdownTargets
from gametime.tracker import Sample


class ActivityProfileTests(unittest.TestCase):
    def test_profiles_are_validated_local_and_keep_legacy_appearance_as_fallback(self):
        from gametime.preferences_sync import LOCAL_FIELDS
        self.assertIn('activity_overlays',LOCAL_FIELDS)
        for profiles in ([],{'site:EXAMPLE.COM':{}},{'app:relative/path.exe':{}},{'category:apps':{}},
                         {'site:example.com':{'seconds':10}},{'site:example.com':{'overlay_enabled':1}},
                         {'site:example.com':{'overlay_x':2}}):
            with self.subTest(profiles=profiles),self.assertRaises(ValueError): replace(Settings(),activity_overlays=profiles).validate()
        members=[target('site','example.com'),target('site','other.com')]
        rule=new_rule('Shared',members,'shared'); rule['enabled']=True
        old=replace(Settings(),wellbeing_rules=[rule],counter_overlays={'shared':{'overlay_font_size':35,'overlay_x':.3}}).validate()
        updated=replace(old,activity_overlays={'site:example.com':{'overlay_font_size':22,'overlay_enabled':False}}).validate()
        self.assertEqual(activity_settings(updated,members[1]).overlay_font_size,35)
        self.assertEqual(activity_settings(updated,members[0]).overlay_x,.3)
        self.assertFalse(activity_settings(updated,target('site','video.example.com')).overlay_enabled)
        self.assertEqual(updated.wellbeing_rules,old.wellbeing_rules); self.assertEqual(updated.counter_overlays,old.counter_overlays)


class ActivityLibraryTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def configure(self,members):
        rule=new_rule('Shared activities',members,'shared'); rule.update(enabled=True,seconds=120)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[rule])
        self.store.save_settings(self.app.settings); self.app.budget_editor.saved(self.app.settings)
        return rule

    def test_three_categories_list_observed_and_configured_activities_without_creating_budgets(self):
        member=target('app',r'C:\Apps\editor.exe'); self.configure([member,target('site','example.com')])
        with self.store.db:
            self.store.db.execute('INSERT INTO activity_items VALUES (?,?,?)',('site','other.com','other.com'))
        before=self.store.settings(); self.app.open_activities('site'); self.pump(.02)
        self.assertEqual(self.app.nav[0].text(),self.app.t('Activities'))
        self.assertEqual(set(self.app.activity_categories),{'game','app','site'})
        listing=self.app.activity_lists['site']; self.assertEqual(listing.list.count(),2)
        self.assertTrue(listing.countdown.isEnabled()); listing.list.setCurrentRow(1)
        self.assertFalse(listing.countdown.isEnabled())
        self.app.open_activities('app'); self.assertEqual(self.app.activity_lists['app'].list.count(),1)
        self.assertEqual(self.store.settings(),before)
        self.app.open_budget(); self.app.budget_editor.show_editor('shared')
        self.assertFalse(self.app.budget_editor.overlay.isVisible()); self.assertFalse(self.app.budget_editor.appearance.isVisible())

    def test_add_website_then_budget_then_appearance(self):
        self.app.open_activities('site'); listing=self.app.activity_lists['site']
        with patch('gametime.qt_activities.QInputDialog.getText',return_value=('https://Example.com/watch?v=1',True)):
            self.app.add_activity()
        self.assertEqual(listing.selected(),target('site','example.com')); self.assertFalse(listing.countdown.isEnabled())
        listing.budget.click(); self.app.budget_editor.minutes.setValue(20); self.app.save_budgets()
        self.app.open_activities('site'); listing.countdown.click()
        window=self.app._dialogs[-1]; self.assertEqual(window.windowTitle(),self.app.t('Custom countdowns'))
        self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],1200); window.reject()

    def test_targets_are_activities_even_when_only_a_mixed_group_budget_exists(self):
        members=[target('game',self.games[0].id),target('site','example.com'),target('app',r'C:\Apps\editor.exe')]
        rule=self.configure(members); self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_budget_enabled=False)
        rows=CountdownTargets(self.app).rows(); keys={key for name,key in rows}
        self.assertEqual(keys,{self.games[0].id,'site:example.com',activity_key(members[2])})
        self.app.game_countdown_dialog(self.games[0].id)
        self.assertEqual(len(self.app._dialogs),1); self.app._dialogs[-1].reject()
        settings=replace(self.app.settings,counter_overlays={'shared':{'overlay_font_size':32}},game_overlays={self.games[0].id:{'overlay_font_size':44}})
        self.assertEqual(activity_settings(settings,members[0],rule).overlay_font_size,44)

    def test_live_shared_budget_uses_foreground_members_style_and_hiding_one_keeps_accounting(self):
        members=[target('app',r'C:\Apps\editor.exe'),target('app',r'C:\Apps\reader.exe')]; self.configure(members)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,activity_overlays={
            activity_key(members[0]):{'overlay_font_size':40,'overlay_color_normal':'#ff0000'},
            activity_key(members[1]):{'overlay_font_size':20,'overlay_color_normal':'#00ff00'}})
        now=datetime.now().astimezone(); first=Sample(now,100,members[0]['value'],'fixture:first')
        self.app.wellbeing.tick(first)
        with patch('gametime.qt_ui.win32.sample',return_value=first):
            self.app.update_overlay(); self.assertEqual(self.app.overlay.font_size,40)
        second=Sample(now+timedelta(seconds=1),101,members[1]['value'],'fixture:second'); self.app.wellbeing.tick(second)
        with patch('gametime.qt_ui.win32.sample',return_value=second):
            self.app.update_overlay(); self.assertEqual(self.app.overlay.font_size,20); self.assertEqual(self.app.overlay.seconds,119)
        profiles=dict(self.app.settings.activity_overlays); profiles[activity_key(members[1])]={'overlay_enabled':False}
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,activity_overlays=profiles)
        third=replace(second,wall=now+timedelta(seconds=2),awake=102); self.app.wellbeing.tick(third)
        with patch('gametime.qt_ui.win32.sample',return_value=third): self.app.update_overlay()
        self.assertFalse(self.app.overlay.isVisible()); self.assertEqual(self.app.wellbeing.active()[0].used,2)

    def test_hidden_library_does_not_poll_or_rebuild_activities(self):
        self.configure([target('site','example.com')]); self.app.open_activities('site')
        listing=self.app.activity_lists['site']
        with patch.object(listing.list,'clear') as rebuild:
            listing.refresh(); listing.refresh(); rebuild.assert_not_called()
        self.app.hide()
        with patch.object(listing,'refresh') as refresh:
            self.app.render_tick(); self.app.render_tick(); refresh.assert_not_called()

    def test_all_icons_preload_without_rebuild_replacement_or_selection_changes(self):
        with self.store.db:
            self.store.db.executemany('INSERT INTO activity_items VALUES (?,?,?)',
                [('app',f'c:\\missing\\app{i:03}.exe',f'App {i:03}') for i in range(100)])
        self.app.open_activities('app'); listing=self.app.activity_lists['app']
        for _ in range(40):
            self.pump(.05)
            if len(listing.icons.resolved)==100: break
        self.assertEqual(len(listing.icons.resolved),100)
        self.assertEqual(len(listing.icons.wanted),100)
        self.assertFalse(listing.list.item(0).icon().isNull()); self.assertFalse(listing.icon_label.pixmap().isNull())
        selected=listing.selected(); key=activity_key(selected)
        item=listing.list.currentItem()
        with patch.object(listing.list,'clear') as rebuild,patch.object(item,'setIcon') as replace_icon:
            listing.icons.changed.emit(key); listing.load_visible_icons()
            self.assertEqual(listing.selected(),selected); rebuild.assert_not_called(); replace_icon.assert_not_called()
        listing.list.scrollToBottom(); self.pump(.05)
        self.assertEqual(len(listing.icons.wanted),100)
        listing.search.setText('no match'); self.pump(.03); self.assertEqual(len(listing.icons.wanted),100)
        self.app.open_activities('site'); self.assertFalse(listing.icons.timer.isActive()); self.assertFalse(listing.icons.jobs)

    def test_versions_and_linked_computers_share_one_activity_and_budget_target(self):
        from gametime.statistics_sync import local_group
        group='ab'*16; old=r'c:\old\editor.exe'; current=r'c:\new\editor.exe'; remote=r'd:\apps\editor.exe'
        self.configure([target('app',old)])
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=group,
            activity_overlays={'app:'+old:{'overlay_font_size':37}})
        with self.store.db:
            self.store.db.executemany('INSERT INTO activity_items VALUES (?,?,?)',
                [('app',old,'Editor.exe'),('app',current,'editor.exe'),('app',r'c:\downloads\editor-2.31.2-setup.exe','Editor-2.31.2-Setup.exe'),
                 ('site','www.example.com','www.example.com'),('site','example.com','example.com')])
            self.store.db.executemany('INSERT INTO statistics_activity VALUES (?,?,?,?,?,?,?)',
                [(local_group(group),'a'*32,'2026-10-28','app',remote,'EDITOR.EXE',10),
                 (local_group(group),'a'*32,'2026-10-28','site','remote.example.com','remote.example.com',10),
                 (local_group('cd'*16),'b'*32,'2026-10-28','site','private.example.com','private.example.com',10)])
        self.app.open_activities('app'); listing=self.app.activity_lists['app']
        self.assertEqual(listing.list.count(),1); self.assertEqual(listing.selected(),target('app','editor.exe'))
        self.assertEqual(set(listing.icons.sources['app:editor.exe']),{old,current,remote,r'c:\downloads\editor-2.31.2-setup.exe'})
        self.assertTrue(listing.countdown.isEnabled())
        self.assertEqual(activity_settings(self.app.settings,target('app',remote)).overlay_font_size,37)
        self.app.budget_editor.open_member(target('app',remote)); self.assertEqual(len(self.app.budget_editor.rules),1)
        self.app.open_activities('site'); self.assertEqual(self.app.activity_lists['site'].list.count(),2)
        before=self.store.db.total_changes
        self.assertEqual(len(known_activities(self.store,replace(self.app.settings,statistics_sync_enabled=False),self.app.catalog)),2)
        self.assertEqual(self.store.db.total_changes,before)

    def test_editing_merged_countdown_replaces_old_aliases_and_all_versions_use_it(self):
        old=target('app',r'c:\old\editor.exe'); new=target('app',r'd:\apps\editor.exe'); self.configure([old])
        self.app.settings=replace(self.app.settings,activity_overlays={
            'app:'+old['value']:{'overlay_font_size':25},'app:'+new['value']:{'overlay_font_size':30}})
        targets=CountdownTargets(self.app); updated=targets.candidate('app:editor.exe',{'overlay_font_size':40})
        self.assertEqual(updated.activity_overlays,{'app:editor.exe':{'overlay_font_size':40}})
        self.assertEqual(activity_settings(updated,old).overlay_font_size,40)
        self.assertEqual(activity_settings(updated,new).overlay_font_size,40)


if __name__=='__main__': unittest.main()
