"""Inherited group rows stay live, explain their source and never become manual rules."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from datetime import datetime,timedelta
from PySide6.QtCore import Qt
from gametime.focus import FocusSettings
from gametime.model import Game
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target
import test_qt_ui as fixture


class FocusGroupMemberTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def entries(self,kind):
        listing=self.app.focus_page.block_lists[kind]
        return {listing.item(i).data(Qt.UserRole):listing.item(i) for i in range(listing.count())}

    def configure(self,groups,**kwargs):
        self.app.focus.configure(FocusSettings(block_groups=groups,**kwargs)); self.app.focus_page.refresh(force=True)

    def test_mixed_members_in_both_tabs_sources_duplicates_and_safe_removal(self):
        first=new_rule('Entertainment',[target('site','youtube.com'),target('app','editor.exe'),target('game',self.games[0].id)],'first')
        second=new_rule('Evening',[target('site','youtube.com'),target('app','editor.exe')],'second')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[first,second])
        self.configure(['budget:first','budget:second']); sites=self.entries('site'); apps=self.entries('app')
        self.assertEqual(set(sites),{'youtube.com'}); self.assertEqual(len(apps),2)
        self.assertEqual(sites['youtube.com'].data(Qt.UserRole+2),['Entertainment','Evening'])
        self.assertIn(self.games[0].name,apps['member:game:'+self.games[0].id].text())
        self.assertIn('editor.exe',apps['member:app:editor.exe'].text())
        self.assertEqual(self.app.focus.settings.block_sites,[]); self.assertEqual(self.app.focus.settings.block_apps,[])
        before=self.store.db.total_changes; page=self.app.focus_page; page.rule_tabs.setCurrentIndex(0)
        page.block_lists['site'].setCurrentItem(sites['youtube.com']); self.assertFalse(page.remove_rule_button.isEnabled())
        page.remove_rule(); self.assertEqual(self.store.db.total_changes,before)
        self.assertIn(self.app.t('This entry comes from a group. Change its members in Budgets or remove the group under Groups.'),page.rules_hint.text())

    def test_direct_and_inherited_members_merge_but_removing_direct_keeps_group(self):
        group=new_rule('Web',[target('site','youtube.com')],'web')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[group])
        self.configure(['budget:web'],block_sites=['youtube.com'])
        page=self.app.focus_page; listing=page.block_lists['site']; self.assertEqual(listing.count(),1)
        listing.setCurrentRow(0); self.assertTrue(page.remove_rule_button.isEnabled()); self.assertTrue(listing.item(0).data(Qt.UserRole+1))
        page.remove_rule(); self.assertEqual(listing.count(),1); self.assertFalse(listing.item(0).data(Qt.UserRole+1))
        self.assertEqual(self.app.focus.settings.block_sites,[]); self.assertEqual(self.app.focus.settings.block_groups,['budget:web'])
        self.assertTrue(self.app.focus.settings.site_blocked('youtube.com',[group]))
        page.rule_tabs.setCurrentIndex(2); page.block_lists['group'].setCurrentRow(0); page.remove_rule()
        self.assertEqual(listing.count(),0); self.assertEqual(self.app.settings.wellbeing_rules,[group])

    def test_saved_group_membership_and_rename_update_without_copying_or_catalog_reads(self):
        group=new_rule('Old',[target('site','youtube.com')],'web')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[group]); self.configure(['budget:web'])
        group['name']='New'; group['members']=[target('site','chess.com')]
        with patch.object(self.store,'games',side_effect=AssertionError('No game DB reads')): self.app.focus_page.refresh()
        self.assertEqual(set(self.entries('site')),{'chess.com'})
        self.assertEqual(self.entries('site')['chess.com'].data(Qt.UserRole+2),['New'])
        self.assertEqual(self.app.focus.settings.block_sites,[])
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[]); self.app.focus_page.refresh()
        self.assertEqual(self.entries('site'),{}); self.assertEqual(len(self.entries('group')),1)

    def test_whole_games_group_expands_live_catalog_in_applications(self):
        self.configure(['games']); self.assertEqual(len(self.entries('app')),len(self.games))
        added=Game('new','New game','Steam',str(self.base/'new'))
        self.app.catalog.games[added.id]=added; self.app.focus_page.refresh()
        self.assertIn('member:game:new',self.entries('app'))
        self.app.catalog.overrides[added.id]=False; self.app.focus_page.refresh()
        self.assertIn(self.app.t('Excluded from group blocking.'),self.entries('app')['member:game:new'].toolTip())
        del self.app.catalog.games[added.id]; self.app.focus_page.refresh(); self.assertNotIn('member:game:new',self.entries('app'))

    def test_categories_use_cached_known_inventory_and_pending_new_members(self):
        with self.store.db:
            self.store.db.executemany('INSERT OR REPLACE INTO activity_items VALUES (?,?,?)',[
                ('site','youtube.com','youtube.com'),('app',str(self.base/'editor.exe'),'Editor'),('app',str(self.base/'skip.exe'),'Excluded')])
        self.configure(['apps','sites'],excluded_apps=[str(self.base/'skip.exe')])
        self.assertEqual(set(self.entries('site')),{'youtube.com'})
        self.assertEqual(set(self.entries('app')),{'member:app:editor.exe'})
        queries=[]; self.store.db.set_trace_callback(queries.append); page=self.app.focus_page
        with patch.object(page.block_lists['app'],'clear') as rebuild:
            for _ in range(5): page.refresh()
            rebuild.assert_not_called()
        self.store.db.set_trace_callback(None); self.assertFalse(any('activity_items' in query for query in queries))
        now=datetime.now().astimezone(); self.app.focus._credit('site','chess.com','chess.com',now,now+timedelta(seconds=1),1)
        page.refresh(); self.assertEqual(set(self.entries('site')),{'youtube.com','chess.com'})
        self.app.focus.flush(); page.refresh(); self.assertEqual(set(self.entries('site')),{'youtube.com','chess.com'})

    def test_group_projection_does_not_change_focus_policy_or_manual_rules(self):
        group=new_rule('Mixed',[target('category','games'),target('site','youtube.com')],'mixed')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[group])
        self.configure(['budget:mixed'],block_apps=[str(self.exe)])
        before=self.app.focus.settings; self.app.focus.start(0); policy=self.app.focus.policy([group]); count=self.store.db.total_changes
        self.app.focus_page.refresh(); self.assertEqual(self.app.focus.settings,before); self.assertEqual(self.app.focus.policy([group]),policy)
        self.assertEqual(self.store.db.total_changes,count)
        matches=[item for item in self.entries('app').values() if item.data(Qt.UserRole)==str(self.exe).lower()]
        self.assertEqual(len(matches),1); self.assertTrue(matches[0].data(Qt.UserRole+1)); self.assertTrue(matches[0].data(Qt.UserRole+2))
