"""Paired extension controls, dispatched onto the desktop's existing Qt thread.

No database connection or application object is used from an HTTP worker.
Only explicit commands mutate state; reads never start programs or focus timers.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict,replace
from datetime import datetime,timedelta
import hashlib,json,math,re,threading,time
from PySide6.QtCore import QObject,Signal,Qt

from . import __version__
from .focus import FocusSettings

READS={'companion.export','state','live','statistics','applications','library.summary','library.icons','artwork','sync.state','update.state'}
GENERAL={'games_root','steam_roots','epic_manifest_dirs','ubisoft_roots','hub_enabled','language',
         'check_updates','budget_reset_minute','overlay_enabled','overlay_replace_warning','limit_popup_enabled',
         'overlay_opacity','overlay_font_size','overlay_color_normal','overlay_color_warning','overlay_x','overlay_y',
         'overlay_screen','overlay_rtss_auto','overlay_rtss_details','notification_sound','notification_sound_path',
         'statistics_device_name','pause_when_idle','idle_timeout_seconds','media_prevents_idle'}
APPEARANCE={'overlay_enabled','overlay_x','overlay_y','overlay_font_size','overlay_screen','overlay_color_normal','overlay_color_warning','overlay_opacity','overlay_rtss_auto'}


def clean(value):
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    return value


class BrowserControl(QObject):
    queued=Signal(object)

    def __init__(self,app):
        super().__init__(app); self.app=app; self.completed=OrderedDict(); self.cache={}
        self.lock=threading.Lock(); self.pending=0
        from .browser_sync_control import SyncControl
        self.sync=SyncControl(self)
        from .browser_library_control import LibraryControl
        self.library=LibraryControl(app)
        self.queued.connect(self.execute,Qt.QueuedConnection)

    def request(self,data):
        ticket={'data':data,'event':threading.Event(),'cancelled':False,'started':False}
        with self.lock:
            if self.pending>=16: return {'ok':False,'error':'Too many requests. Try again.'}
            self.pending+=1
        self.queued.emit(ticket)
        if not ticket['event'].wait(8):
            with self.lock: ticket['cancelled']=True
            return {'ok':False,'error':'The application is busy. Refresh before trying again.','uncertain':ticket['started']}
        return ticket['answer']

    def execute(self,ticket):
        try:
            with self.lock:
                if ticket['cancelled']: return
                ticket['started']=True
            ticket['answer']=self.dispatch(ticket['data'])
        finally:
            with self.lock: self.pending-=1
            ticket['event'].set()

    def revision(self):
        app=self.app
        raw=json.dumps([asdict(app.settings),asdict(app.focus.settings),app.catalog.overrides,
                        app.catalog.rules,sorted(app.store.hidden_ids()),app.overlay_consents.display_enabled,app.background_media.members,
                        [(g.id,g.name,g.installed) for g in app.catalog.games.values()]],sort_keys=True,ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def dispatch(self,request):
        try:
            if set(request)-{'action','data','revision','id'}: raise ValueError('Invalid request.')
            action=request.get('action'); data=request.get('data',{})
            if not isinstance(action,str) or not isinstance(data,dict): raise ValueError('Invalid request.')
            if getattr(self.app,'closed',False): raise ValueError('The application is closing.')
            # Journal imports have their own durable sequence and timer tokens.
            mutating=action not in READS and action not in ('continuity.exchange','choices.status','choices.choose')
            identity=request.get('id','')
            if mutating:
                if not isinstance(identity,str) or not re.fullmatch('[a-zA-Z0-9-]{16,80}',identity): raise ValueError('Invalid request.')
                signature=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
                if identity in self.completed:
                    previous,result=self.completed[identity]
                    if previous!=signature: raise ValueError('Invalid request.')
                    return result
                if request.get('revision')!=self.revision():
                    return {'ok':False,'conflict':True,'error':self.app.t('Settings changed in another window. Refresh before saving; your draft is kept.')}
            from . import companion_transfer
            from . import browser_choices
            handlers={'companion.export':lambda data:companion_transfer.export(self.app,data),'companion.import':lambda data:companion_transfer.receive(self.app,data),'continuity.exchange':self.continuity_exchange,'state':self.state,'live':self.live,'statistics':self.statistics,'applications':self.applications,'library.summary':lambda data:self.library.summary(),'library.icons':self.library.activity_icons,'artwork':self.library.artwork,
                      'settings.save':self.settings_save,'focus.save':self.focus_save,'focus.start':self.focus_start,
                      'focus.pause':self.focus_pause,'focus.stop':self.focus_stop,'budget.save':self.budget_save,
                      'budget.delete':self.budget_delete,'notification.save':self.notification_save,
                      'notification.delete':self.notification_delete,'notification.preview':self.notification_preview,'notification.action':self.notification_action,
                      'activity.change':self.activity_change,'activity.media':self.activity_media,'activity.appearance':self.activity_appearance,
                      'game.launch':self.game_launch,'app.open':self.app_open,
                      'sync.state':lambda data:self.sync.state(),'sync.reveal':self.sync.reveal,
                      'sync.generate':self.sync.generate,'sync.command':self.sync.command,'sync.save':self.sync.save,
                      'sync.rename':self.sync.rename,'activity.add':self.library.activity_add,'game.add':self.library.game_add,
                      'rule.save':self.library.rule_save,'rule.delete':self.library.rule_delete,'library.refresh':self.library.refresh,
                      'game.removal':self.library.removal,'icon.upload':self.library.upload_icon,'update.command':self.library.update,
                      'update.state':lambda data:self.library.update({'action':'status'}),'display.consent':self.library.display_consent,
                      'choices.status':lambda data:browser_choices.request(self.app,data),
                      'choices.choose':lambda data:browser_choices.request(self.app,data,True),
                      'break.start':self.break_start}
            if action not in handlers: raise ValueError('Unknown command.')
            result=clean({'ok':True,'result':handlers[action](data),'revision':self.revision()})
            if mutating:
                self.cache.clear(); self.completed[identity]=(signature,result)
                while len(self.completed)>64: self.completed.popitem(last=False)
            return result
        except (ValueError,TypeError,KeyError,AttributeError) as exc:
            return {'ok':False,'error':str(self.app.t(str(exc))) if isinstance(exc,ValueError) else str(self.app.t('Invalid request.'))}
        except Exception:
            # Never return stack traces, filesystem/database contents or secrets.
            return {'ok':False,'error':str(self.app.t('Could not save settings. Try again.'))}

    def live(self,data):
        app=self.app; focus=app.focus
        from .schedule import current_day
        return dict(version=__version__,language=app.settings.language,day=current_day(app.settings).isoformat(),
                    focus=dict(running=focus.running,finished=focus.finished,phase=focus.phase,remaining=focus.remaining,
                               rounds=focus.completed_rounds,today=focus.completed_on(focus.day(datetime.now().astimezone()))),
                    timers=[dict(asdict(item),label=str(item.label(app.t)),detail=str(item.secondary(app.t))) for item in app.timer_views(wall=datetime.now().astimezone())],
                    break_actions=app.restrictions.early_break_actions(),
                    revision=self.revision(),sync_busy=bool(getattr(app,'_sync_busy',False)))

    def continuity_exchange(self,data):
        from . import win32
        # Close the current native interval before returning a durable receipt.
        self.app.focus_tick(win32.sample())
        return self.app.browser_continuity.exchange(data)

    def break_start(self,data):
        if set(data)!={'key','step'} or not all(isinstance(data[k],str) for k in data):raise ValueError('Invalid request.')
        if not self.app.restrictions.start_early_break(data['key'],data['step']):raise ValueError('This break is no longer available.')
        return True

    def state(self,data):
        app=self.app; settings=app.settings
        from .activities import known_activities
        from .notification_text import KINDS
        from .notification_rules import builtin,normalized,title,message,ICONS,TRIGGERS
        from .focus_members import rows
        from .restriction_policy import new_plan,step
        from .overlay_consent import DISPLAY_NOTICE
        hidden=app.store.hidden_ids()
        from .activity_identity import activity_key
        from PySide6.QtWidgets import QApplication
        all_focus_sites,focus_sites=app.focus.settings.site_rules(settings.wellbeing_rules)
        sources={}; activities=known_activities(app.store,settings,app.catalog,sources)
        games=[dict(asdict(game),enabled=app.catalog.enabled(game),hidden=game.id in hidden) for game in self.library.games().values()]
        inventory={(kind,key):name for kind,key,name in app.store.db.execute('SELECT kind,key,name FROM activity_items')}
        inventory.update(app.focus.items)
        names={'games':app.t('All games'),'apps':app.t('All applications'),'sites':app.t('All websites'),
               **{'budget:'+r['id']:r['name'] for r in settings.wellbeing_rules}}
        notifications=[]
        for key,item in [(('builtin:'+kind),builtin(settings,kind)) for kind in KINDS]+[('scheduled:'+r['id'],r) for r in settings.scheduled_notifications]:
            if item: notifications.append(dict(key=key,value=normalized(item),title=title(item,app.t),message=message(item,settings)))
        icon_entries=list(activities)
        icon_entries += [(dict(kind=kind,value=value),value) for kind,values in (('app',app.focus.settings.block_apps),('site',app.focus.settings.block_sites)) for value in values]
        icon_entries += [(dict(kind=kind,value=value),name) for (kind,value),name in inventory.items() if kind in ('app','site')]
        icon_entries += [(dict(kind='app',value=n['value']['action']['path']),n['title']) for n in notifications if n['value']['action']['kind']=='app']
        self.library.register_icons(icon_entries,sources,reset=True)
        self.library.notification_images={n['key']:n['value']['icon'] for n in notifications}
        return dict(background_media=deepcopy(app.background_media.members),live=self.live({}),settings={k:deepcopy(getattr(settings,k)) for k in GENERAL},
                    focus=asdict(app.focus.settings),focus_site_rules=dict(all=all_focus_sites,domains=focus_sites),activity_appearances=deepcopy(settings.activity_overlays),members=rows(app.focus.settings,settings.wellbeing_rules,app.catalog,inventory,names,app.t),
                    groups=[dict(id=k,name=str(v)) for k,v in names.items()],games=games,library=self.library.summary(),
                    activities=[dict(member=member,name=name,excluded=member['kind']=='app' and all(app.focus.settings.app_excluded(path) for path in sources[activity_key(member)]))
                                for member,name in activities],
                    budgets=self.budgets(),notifications=notifications,
                    presets=[dict(key='builtin:'+kind,value=normalized(builtin(replace(settings,removed_notifications=[]),kind))) for kind in KINDS],
                    icons=[dict(id=k,name=str(app.t(v))) for k,v in ICONS.items()],triggers=[dict(id=k,name=str(app.t(v))) for k,v in TRIGGERS.items()],
                    default_plan=new_plan(legacy=False),default_step=step('cover',0),
                    sync=self.sync.state(),device_scopes=self.device_scopes(),executable_rules=dict(app.catalog.rules),
                    protected_display=dict(enabled=app.overlay_consents.display_enabled,notice=str(app.t(DISPLAY_NOTICE))),
                    screens=[screen.name() for screen in QApplication.screens()])

    def device_scopes(self):
        from .qt_device_scope import devices
        from .device_scopes import connection
        s=self.app.settings
        return dict(local=s.scope_device,connection=connection(s.statistics_sync_group),devices=[dict(id=id,name=str(name)) for id,name in devices(self.app)],groups=deepcopy(s.device_groups))

    def budgets(self):
        s=self.app.settings
        from .computer_periods import FIELDS
        from .restriction_policy import legacy_active,legacy_warning_active,legacy_restriction_active
        entries=[]
        if s.game_budget_enabled: entries.append(dict(key='shared-games',kind='shared',name=str(self.app.t('Games · shared budget')),seconds=s.limit_seconds,enabled=True,overlay=s.overlay_enabled,members=[{'kind':'category','value':'games'}]))
        for gid,seconds in s.game_limits.items():
            game=self.app.catalog.games.get(gid)
            entries.append(dict(key='game:'+gid,kind='game',name=game.name if game else gid,seconds=seconds,enabled=True,overlay=s.game_overlays.get(gid,{}).get('overlay_enabled',s.overlay_enabled),members=[{'kind':'game','value':gid}]))
        entries += [dict(deepcopy(rule),key=rule['id'],kind='group') for rule in s.wellbeing_rules]
        if s.bedtime_enabled: entries.append(dict(key='computer-window',kind='computer',name=str(self.app.t('Computer use')),values={k:getattr(s,k) for k in FIELDS},enabled=True,members=[]))
        entries += [dict(key=p['id'],kind='computer',name=p['name'],values=deepcopy(p['values']),enabled=p['values']['bedtime_enabled'],members=[]) for p in s.computer_periods]
        running={budget.key:budget for budget in self.app.restrictions.budgets(datetime.now().astimezone())}
        for entry in entries:
            key=entry['key']; entry.update(days=s.budget_active_days.get(key,list(range(7))),usage=s.budget_usage_limits.get(key,True),
                plan=deepcopy(s.restriction_plans.get(key)),appearance=deepcopy(s.game_overlays.get(key[5:],{}) if key.startswith('game:') else s.counter_overlays.get(key,{})))
            if key in s.budget_devices:entry['devices']=deepcopy(s.budget_devices[key])
            entry['legacy']=dict(active=legacy_active(s.restriction_plans,key),warning=key=='shared-games' and legacy_warning_active(s.restriction_plans,key),
                warning_seconds=s.warning_seconds,restriction=key=='shared-games' and legacy_restriction_active(s.restriction_plans,key) and s.restriction_enabled,
                restriction_seconds=s.restriction_seconds,enforce=(s.restriction_plans.get(key) or {}).get('legacy_enforce',True) if key.startswith('game:') else entry.get('enforce',False))
            budget=running.get(key);entry['used']=budget.used if budget else 0
            entry['remaining']=max(0,budget.limit-budget.used) if budget else None
        return entries

    def statistics(self,data):
        app=self.app
        from .statistics import summarize,date_range
        from .schedule import current_day
        end=data.get('end',current_day(app.settings).isoformat()); start=data.get('start',end)
        date_range(start,end); category=data.get('category','all'); scope=data.get('scope','all')
        if category=='sites': category='websites'  # Older browser clients.
        if category not in ('all','games','apps','websites') or not isinstance(scope,str) or len(scope)>100: raise ValueError('Invalid request.')
        key=(start,end,category,scope,app.settings.statistics_sync_group,app.settings.language,getattr(app.store,'statistics_revision',0)); cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<10: return cached[1]
        app.tracker.flush(); app.focus.flush(); db=app.statistics_data; group=app.settings.statistics_sync_group
        rows=[]; started=db.started_on(group,scope)
        if category in ('all','games'): rows+=db.history_by_computer(start,end,group,scope,app.settings.statistics_device_name)
        if category!='games':
            rows+=db.activity_history_by_computer(start,end,group,scope,category,app.settings.statistics_device_name)
            other=db.activity_started_on(group,scope); started=min(started,other) if category=='all' else other
        report=summarize((row[:5] for row in rows),start,end,started_on=started,as_of=current_day(app.settings).isoformat())
        from collections import Counter
        from .statistics_sync import computer_name
        aliases=db.device_aliases(group); devices=[(identity,aliases.get(identity,name),since) for identity,name,since in db.devices(group)]
        counts=Counter(name for identity,name,since in devices)
        names={'local':str(app.t('{name} (this computer)',name=app.settings.statistics_device_name or computer_name()))}
        names.update({identity:name+(' · '+identity[:8] if counts[name]>1 else '') for identity,name,since in devices})
        # Allocate in the same stable order as the desktop chart.
        for identity in sorted(names): app.statistics.colors.color(identity,'computer')
        for identity in sorted(row[0] for row in report.games): app.statistics.colors.color(identity,'game')
        result=dict(asdict(report),total=report.total,average=report.average,computers=db.devices(group),rows=rows,
                    sessions=db.session_data(group,scope),session_start=start,
                    started=max(started,start),computer_names=names,computer_colors={identity:app.statistics.colors.color(identity,'computer') for identity in names},
                    colors={row[0]:app.statistics.colors.color(row[0],'game') for row in report.games})
        self.cache[key]=(time.monotonic(),result)
        while len(self.cache)>12: self.cache.pop(next(iter(self.cache)))
        return result

    def applications(self,data):
        from .notification_applications import choices
        entries=choices(self.app)
        self.library.register_icons([(dict(kind='app',value=path),name) for path,name in entries])
        return [dict(path=path,name=name) for path,name in entries]

    def save(self,settings):
        from .global_day_start import normalize,carry_markers
        from .computer_periods import carry_runtime
        from .qt_day_start import apply_day_start
        app=self.app; previous=app.settings; settings=normalize(settings).validate()
        if app.settings_have_draft(): raise ValueError('Save or discard the open desktop settings draft before changing settings here.')
        app.tracker.flush(); app.wellbeing.flush(); app.store.save_settings(settings)
        app.settings=app.catalog.settings=settings
        carry_markers(app.store,previous,settings); carry_runtime(app.store,previous,settings)
        app.renewal_settings_changed(previous,settings); apply_day_start(app,previous)
        app._wellbeing_grace=None; app._restriction_grace=None
        app.tracker.evaluate(datetime.now().astimezone()); app.restrictions.prepare(datetime.now().astimezone())
        app.update_focus_policy(); app.update_overlay(); app.last_rows=None
        # Rebuild clean native forms after an explicit remote save, never on polls.
        selected=app.pages.currentIndex()
        app.budget_editor.drafts.close()
        old=app.settings_page; replacement=app._build_settings()
        app.pages.insertWidget(2,replacement); app.pages.removeWidget(old); app.settings_page=replacement; old.deleteLater()
        old=app.budget_page; replacement=app._build_budget_page()
        app.pages.insertWidget(5,replacement); app.pages.removeWidget(old); app.budget_page=replacement; old.deleteLater()
        app.pages.setCurrentIndex(selected)
        if previous.games_root!=settings.games_root or any(getattr(previous,k)!=getattr(settings,k) for k in ('steam_roots','epic_manifest_dirs','ubisoft_roots','hub_enabled')):
            app.service.configure(settings)
        if previous.language!=settings.language:
            from .qt_translation import retranslate_widgets
            retranslate_widgets(app,settings.language)
            blocked=app.language.blockSignals(True); app.language.setCurrentIndex(app.language.findData(settings.language)); app.language.blockSignals(blocked)
            app.statistics.retranslate_report()
        app.notifications_page.refresh(); app.focus_page.refresh(force=True); app.updates.saved()
        if app.isVisible(): app.render()

    def settings_save(self,data):
        if set(data)-GENERAL-{'tracking'}: raise ValueError('Invalid request.')
        data=dict(data); tracking=data.pop('tracking',self.app.focus.settings.tracking)
        focus=replace(self.app.focus.settings,tracking=tracking).validate()
        self.save(replace(self.app.settings,**data))
        self.app.focus.configure(focus); self.app.activity_tracking.setChecked(tracking); self.app.update_focus_policy(); return True

    def focus_save(self,data):
        if set(data)-set(asdict(self.app.focus.settings)): raise ValueError('Invalid focus settings.')
        self.app.focus.configure(replace(self.app.focus.settings,**data)); self.app.update_focus_policy(); return True

    def focus_start(self,data): self.app.focus.start(self.app.focus_awake()); self.app.update_focus_policy(); return self.live({})
    def focus_pause(self,data): self.app.focus.pause(self.app.focus_awake()); self.app.update_focus_policy(); return self.live({})
    def focus_stop(self,data): self.app.focus.stop(); self.app.update_focus_policy(); return self.live({})

    def budget_save(self,data):
        s=self.app.settings; key=data['key']; kind=data['kind']
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_:.-]{1,2100}',key): raise ValueError('Invalid budget.')
        values={}; days=deepcopy(s.budget_active_days); usage=dict(s.budget_usage_limits); plans=deepcopy(s.restriction_plans)
        days[key]=data.get('days',list(range(7))); usage[key]=data.get('usage',True)
        if data.get('devices') is not None:
            from .device_scopes import normalize
            values['budget_devices']={**s.budget_devices,key:normalize(data['devices'],s,budget=True)}
        if data.get('plan') is not None: plans[key]=data['plan']
        else: plans.pop(key,None)
        if kind=='shared' and key=='shared-games':
            seconds=data['seconds']; values.update(game_budget_enabled=data['enabled'],limit_seconds=seconds,
                warning_seconds=min(s.warning_seconds,seconds*.8) if seconds else s.warning_seconds,overlay_enabled=data.get('overlay',True))
            if 'legacy' in data:
                legacy=data['legacy']; values.update(restriction_enabled=legacy['restriction'],restriction_seconds=legacy['restriction_seconds'])
                if legacy['warning']: values['warning_seconds']=legacy['warning_seconds']
                if not legacy['warning']:
                    from .restriction_policy import new_plan
                    plans.setdefault(key,new_plan(legacy=True))['legacy_warning']=False
        elif kind=='game' and key.startswith('game:'):
            limits=dict(s.game_limits); limits[key[5:]]=data['seconds']; values['game_limits']=limits
            if 'legacy' in data:
                from .restriction_policy import new_plan
                plans.setdefault(key,new_plan(legacy=True))['legacy_enforce']=data['legacy']['enforce']
        elif kind=='computer':
            from .computer_periods import FIELDS
            fields=data['values']
            if set(fields)!=set(FIELDS): raise ValueError('Invalid computer-use period.')
            if key=='computer-window': values.update(fields)
            else: values['computer_periods']=[p for p in s.computer_periods if p['id']!=key]+[dict(id=key,name=data['name'],values=fields)]
        elif kind=='group':
            rule={k:data[k] for k in ('name','members','seconds','enabled','overlay')}; rule.update(id=key,enforce=data.get('enforce',False))
            from .wellbeing import target
            rule['members']=[target(m['kind'],m['value']) for m in rule['members']]
            values['wellbeing_rules']=[r for r in s.wellbeing_rules if r['id']!=key]+[rule]
        else: raise ValueError('Invalid budget.')
        if 'appearance' in data:
            if not isinstance(data['appearance'],dict) or set(data['appearance'])-APPEARANCE: raise ValueError('Invalid countdown settings.')
            if kind=='shared': values.update(data['appearance'])
            else:
                field='game_overlays' if kind=='game' else 'counter_overlays'; profiles=deepcopy(getattr(s,field)); profiles[key[5:] if kind=='game' else key]=data['appearance']; values[field]=profiles
        self.save(replace(s,**values,budget_active_days=days,budget_usage_limits=usage,restriction_plans=plans,budget_setup_completed=True)); return True

    def budget_delete(self,data):
        key=data['key']; s=self.app.settings
        if key not in {item['key'] for item in self.budgets()}: raise ValueError('Invalid budget.')
        values={}
        if key=='shared-games': values['game_budget_enabled']=False
        elif key=='computer-window': values['bedtime_enabled']=False
        elif key.startswith('game:'): values['game_limits']={k:v for k,v in s.game_limits.items() if k!=key[5:]}
        else:
            values['wellbeing_rules']=[r for r in s.wellbeing_rules if r['id']!=key]
            values['computer_periods']=[p for p in s.computer_periods if p['id']!=key]
        for field in ('budget_active_days','budget_usage_limits','restriction_plans','counter_overlays'):
            values[field]={k:v for k,v in getattr(s,field).items() if k!=key}
        self.save(replace(s,**values)); return True

    def notification_save(self,data):
        from .notification_rules import validate_item,validate_files,BUILTIN_IDS
        from .notification_drafts import apply
        key=data['key']; item=data['value']; validate_item(item); validate_files(item)
        expected=BUILTIN_IDS.get(key.removeprefix('builtin:')) if key.startswith('builtin:') else key.removeprefix('scheduled:') if key.startswith('scheduled:') else None
        if expected!=item['id']: raise ValueError('Invalid notification.')
        self.save(apply(self.app.settings,{key:item})); return True

    def notification_delete(self,data):
        from .notification_drafts import apply,original
        key=data['key']
        if not original(self.app.settings,key): raise ValueError('Invalid notification.')
        self.save(apply(self.app.settings,{key:None})); return True

    def notification_preview(self,data):
        from .notification_rules import validate_item,validate_files
        validate_item(data['value']); validate_files(data['value'])
        # The browser renders its own preview; no startup trigger or app launch.
        return data['value']

    def notification_action(self,data):
        from .notification_rules import validate_action
        action=data['action'];validate_action(action)
        if action['kind']=='app':
            from .qt_notification_options import launch_application
            launch_application(action['path'])
        elif action['kind']=='pomodoro':
            if self.app.focus.running: raise ValueError('A focus timer is already running. Stop it in Focus mode before starting a new one.')
            settings=replace(self.app.focus.settings,**{k:v for k,v in action.items() if k!='kind'}).validate()
            self.app.focus.configure(settings);self.app.focus.stop();self.app.focus.start(self.app.focus_awake())
            self.app.update_focus_policy();self.app.focus_page.refresh(force=True)
        else: raise ValueError('Invalid notification button.')
        return True

    def activity_change(self,data):
        app=self.app; kind=data['kind']; key=data['key']; enabled=data.get('enabled'); hidden=data.get('hidden')
        if kind=='game' and key in {g.id for g in app.store.games()}:
            if enabled is not None:
                if type(enabled) is not bool: raise ValueError('Invalid request.')
                app.store.set_enabled(key,enabled); app.catalog.overrides=app.store.overrides()
            if hidden is not None:
                if type(hidden) is not bool: raise ValueError('Invalid request.')
                app.store.set_hidden(key,hidden); app.hidden_ids=app.store.hidden_ids()
        elif kind=='app' and type(enabled) is bool:
            app.focus.set_app_tracking(key,enabled)
        else: raise ValueError('Invalid request.')
        app.last_rows=None; app.update_focus_policy()
        if app.isVisible(): app.render()
        return True

    def activity_media(self,data):
        self.app.background_media.set_enabled({'kind':data.get('kind'),'value':data.get('key')},data.get('enabled'))
        self.app.refresh_activity_lists();return True

    def activity_appearance(self,data):
        from .activities import activity_target
        from .activity_identity import activity_key
        key=activity_key(activity_target(data['key'])); profiles=deepcopy(self.app.settings.activity_overlays)
        if data.get('value') is None: profiles.pop(key,None)
        else: profiles[key]=data['value']
        self.save(replace(self.app.settings,activity_overlays=profiles)); return True

    def game_launch(self,data):
        game=self.app.catalog.games.get(data['id'])
        if not game or not game.installed: raise ValueError('Game is not installed.')
        self.app.play_game(game.id); return True

    def app_open(self,data): self.app.show(); return True
