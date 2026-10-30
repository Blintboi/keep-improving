"""Local sound, weekend and game-specific countdown preferences."""
from dataclasses import replace
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPixmap,QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFileDialog,QApplication,QAbstractSpinBox,QColorDialog,QScrollArea,QSizePolicy,QSlider
from .qt_translation import QLineEdit,QCheckBox
from .qt_widgets import label,button,back_button,panel,separator,NoWheelComboBox,NoWheelDoubleSpinBox
from .overlay import PositionPicker,choose_screen
from .game_safety import policy as safety
from .overlay_consent import display_reason
from .schedule import game_settings,day_settings
from .sound import play_notification
from .qt_game_preview import background_controls


def number(value,maximum=1440,decimals=2):
    edit=NoWheelDoubleSpinBox(); edit.setRange(.01,maximum); edit.setDecimals(decimals)
    edit.setButtonSymbols(QAbstractSpinBox.NoButtons); edit.setValue(value); return edit


def sound_panel(app):
    t=app.t; card=panel(); layout=QVBoxLayout(card); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
    layout.addWidget(label(t('Notification sound'),'section'))
    mode=NoWheelComboBox(); mode.setAccessibleName(t('Notification sound'))
    for value,text in (('default','Default sound'),('information','Information sound'),('error','Attention sound'),('silent','Silent'),('custom','Custom WAV file')): mode.addItem(t(text),value)
    mode.setCurrentIndex(mode.findData(app.settings.notification_sound)); layout.addWidget(mode)
    custom=QWidget(); custom_layout=QVBoxLayout(custom); custom_layout.setContentsMargins(0,0,0,0)
    custom_layout.addWidget(label(t('Sound file'),'muted'))
    row=QHBoxLayout(); path=QLineEdit(app.settings.notification_sound_path); path.setAccessibleName(t('Sound file')); path.setReadOnly(True)
    path.setPlaceholderText(t('Choose a WAV sound file.')); row.addWidget(path,1)
    def browse():
        value,_=QFileDialog.getOpenFileName(app,t('Choose notification sound'),path.text(),'WAV (*.wav)')
        if value: path.setText(value); mode.setCurrentIndex(mode.findData('custom'))
    browse_button=button(t('Browse…'),browse); row.addWidget(browse_button); custom_layout.addLayout(row); layout.addWidget(custom)
    error=label('','danger'); error.setWordWrap(True); error.hide(); layout.addWidget(error)
    def values(): return dict(notification_sound=mode.currentData(),notification_sound_path=path.text())
    app.sound_values=values
    def reset_sound(settings):
        path.setText(settings.notification_sound_path); mode.setCurrentIndex(mode.findData(settings.notification_sound))
        error.clear(); error.hide(); stop()
    app.reset_sound=reset_sound
    def preview():
        try:
            settings=replace(app.settings,**values()).validate()
            if not play_notification(settings): raise ValueError('Could not play the sound.')
            error.hide()
        except ValueError as exc: error.setText(t(str(exc))); error.show()
    def stop():
        import winsound
        winsound.PlaySound(None,0)
    layout.addWidget(separator()); actions=QHBoxLayout(); test=button(t('Test sound'),preview); actions.addWidget(test)
    actions.addWidget(button(t('Stop sound'),stop)); actions.addStretch(); layout.addLayout(actions)
    def changed(*args):
        custom.setVisible(mode.currentData()=='custom')
        path.setEnabled(mode.currentData()=='custom'); browse_button.setEnabled(mode.currentData()=='custom')
        test.setEnabled(mode.currentData()!='silent'); error.hide()
    mode.currentIndexChanged.connect(changed); changed()
    mode.setToolTip(t('Applies to game-time and bedtime popups. If a custom file is unavailable, the default sound is used. Save to apply changes.')+'\n\n'+t('Protected fullscreen games use sound instead of popup windows. If sound is set to Silent or fails, the reminder waits until a visual notification is possible.'))
    return card


def game_overlay_dialog(app,gid=None):
    from .qt_ui import dark_window
    from .qt_countdown_targets import CountdownTargets
    for existing in app._dialogs:
        if getattr(existing,'_personalization_kind',None)=='game':
            existing._refresh_games()
            if gid: existing._select_game(gid)
            existing.show(); existing.raise_(); existing.activateWindow(); return
    t=app.t; window=app._dialog(t('Custom countdowns'),780); window.resize(780,min(900,QApplication.primaryScreen().availableGeometry().height()-80))
    window._personalization_kind='game'
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(12)
    layout.addWidget(back_button(t,window.reject),0,Qt.AlignLeft)
    note=label(t('This appearance belongs to the activity. Activities sharing a time budget can have different countdowns.'),'muted'); note.setWordWrap(True); layout.addWidget(note)
    targets=CountdownTargets(app)
    games=NoWheelComboBox(); games.setAccessibleName(t('Countdown target'))
    games.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
    games.setSizeAdjustPolicy(NoWheelComboBox.AdjustToMinimumContentsLengthWithIcon); games.setMinimumContentsLength(24)
    for name,key in targets.rows(): games.addItem(name,key)
    games.setPlaceholderText(t('Choose a countdown.'))
    if gid: games.setCurrentIndex(games.findData(gid))
    window._select_game=lambda value:games.setCurrentIndex(games.findData(value))
    layout.addWidget(label(t('Countdown target'),'muted'))
    select_row=QHBoxLayout(); select_row.addWidget(games,1)
    layout.addLayout(select_row)
    hide_countdown=QCheckBox(t('Hide this countdown')); hide_countdown.setAccessibleName(t('Hide this countdown'))
    layout.addWidget(hide_countdown); layout.addWidget(separator())
    safety_notice=label('','muted'); safety_notice.setWordWrap(True); layout.addWidget(safety_notice)
    risk_button=button(t('Allow game image preview…'),lambda:change_consent()); layout.addWidget(risk_button,0,Qt.AlignLeft)
    minimize_notice=label('','muted'); minimize_notice.setWordWrap(True); layout.addWidget(minimize_notice)
    minimize_button=button(t('Review minimization risks…'),lambda:change_minimize_consent()); layout.addWidget(minimize_button,0,Qt.AlignLeft)
    controls=QWidget(); form=QVBoxLayout(controls); form.setContentsMargins(0,0,0,0); form.setSpacing(10)
    form.addWidget(label(t('Countdown colors'),'section'))
    colors={}; color_buttons={}; color_row=QHBoxLayout()
    for kind,text in (('normal','Normal color'),('warning','Warning color')):
        group=QVBoxLayout(); group.addWidget(label(t(text),'muted'))
        item=button('',lambda checked=False,k=kind:choose_color(k)); item.setAccessibleName(t(text)); color_buttons[kind]=item
        group.addWidget(item); color_row.addLayout(group,1)
    color_row.addWidget(button(t('Default colors'),lambda:reset_colors()),0,Qt.AlignBottom); form.addLayout(color_row)
    form.addWidget(separator()); form.addWidget(label(t('Position and text size'),'section'))
    monitor=NoWheelComboBox(); monitor.setAccessibleName(t('Monitor')); monitor.addItem(t('Automatic'),'')
    for screen in QApplication.screens(): monitor.addItem(screen.name(),screen.name())
    screen_row=QHBoxLayout(); screen_row.addWidget(label(t('Monitor'),'muted')); screen_row.addWidget(monitor,1); form.addLayout(screen_row)
    picker=PositionPicker(1,0,QApplication.primaryScreen()); picker.setAccessibleName(t('Countdown position')); form.addWidget(picker)
    background_row=background_controls(app,picker,lambda:games.currentData(),lambda:monitor.currentData(),lambda:update_coordinates())
    form.addWidget(background_row)
    hint=label(t('Drag the timer or enter its position from the display’s top-left corner. Arrow keys move 1 px; Shift + arrow moves 10 px. Preview shows changes before saving.'),'muted'); hint.setWordWrap(True); form.addWidget(hint)
    row=QHBoxLayout(); coordinates=[]
    for text in ('Horizontal (px)','Vertical (px)'):
        edit=number(16,100000,0); edit.setKeyboardTracking(False); edit.setAccessibleName(t(text)); coordinates.append(edit)
        group=QVBoxLayout(); group.addWidget(label(t(text),'muted')); group.addWidget(edit); row.addLayout(group,1)
    size=number(25,72,0); size.setMinimum(8); size.setSuffix(' pt'); size.setKeyboardTracking(False); size.setAccessibleName(t('Text size'))
    group=QVBoxLayout(); group.addWidget(label(t('Text size'),'muted')); group.addWidget(size); row.addLayout(group,1); form.addLayout(row)
    opacity_row=QHBoxLayout(); opacity_row.addWidget(label(t('Text opacity'),'muted'))
    opacity=QSlider(Qt.Horizontal); opacity.setRange(25,100); opacity.setAccessibleName(t('Text opacity')); opacity_row.addWidget(opacity,1)
    opacity_value=label(''); opacity_row.addWidget(opacity_value); form.addLayout(opacity_row)
    def open_display():
        window.reject(); app.rtss_dialog()
    rtss_button=button(t('In-game display…'),open_display,'quiet'); layout.addWidget(rtss_button,0,Qt.AlignLeft)
    form.addStretch()
    scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame); scroll.setWidget(controls); layout.addWidget(scroll,1)
    blocked_space=QWidget(); layout.addWidget(blocked_space,1)
    drafts=targets.profiles; current=[None]; loading=[False]
    initializing=[False]
    def draft():
        return dict(overlay_enabled=not hide_countdown.isChecked(),overlay_x=picker.x_ratio,overlay_y=picker.y_ratio,overlay_font_size=int(size.value()),overlay_screen=monitor.currentData() or '',overlay_opacity=opacity.value()/100,**colors)
    def candidate():
        return targets.candidate(current[0],draft())
    def update_coordinates():
        for edit,bounds,value in zip(coordinates,picker.pixel_limits(),picker.pixel_position()):
            blocked=edit.blockSignals(True); edit.setRange(*bounds); edit.setValue(value); edit.blockSignals(blocked)
    def changed(*args):
        if loading[0]: return
        game=app.catalog.games.get(current[0]); counter=targets.rule(current[0])
        raw=safety.reason(game=game) if game else None
        reason=display_reason(app.catalog,game=game) if game else None
        opacity_value.setText(str(opacity.value())+'%'); rtss_button.setVisible(bool(game))
        background_row.setVisible(bool(game))
        if counter:
            picker._background_controller.show_timer.stop(); picker._background_controller.target=None; picker.game_background=None
        status.setText(t('Preview shows this countdown on the desktop for 10 seconds.') if counter else t('Preview brings a running game to the foreground. Alt+Tab ends the preview.'))
        accepted=app.overlay_consents.allows(game)
        from .game_safety import PROTECTED,UNCHECKED
        safety_notice.setText(t(reason) if reason==UNCHECKED else
                             t('Anti-cheat game display is enabled on the Notifications page.' if app.overlay_consents.display_enabled else
                               'Enable display in anti-cheat games on the Notifications page.') if raw==PROTECTED else t(raw) if raw else '')
        safety_notice.setVisible(bool(raw))
        requestable=raw==PROTECTED and safety.inspection(game=game)!=UNCHECKED
        risk_button.setVisible(raw==PROTECTED and (accepted or requestable)); risk_button.setText(t('Revoke game image preview permission') if accepted else t('Allow game image preview…'))
        minimize_accepted=app.minimize_consents.allows(game)
        minimize_notice.setText(t('Automatic minimization is allowed for this game. It can interrupt an online match.') if minimize_accepted else
                                t('Automatic minimization is disabled for this game. Reminders do not take focus; automatic Escape stays disabled even with consent.'))
        minimize_notice.setVisible(raw==PROTECTED)
        minimize_button.setText(t('Revoke minimization permission') if minimize_accepted else t('Review minimization risks…'))
        minimize_button.setVisible(raw==PROTECTED and (minimize_accepted or requestable))
        available=bool(counter or game and game.installed) and reason!=UNCHECKED
        hide_countdown.setVisible(available)
        scroll.setVisible(available and not hide_countdown.isChecked()); preview_controls.setVisible(available and not hide_countdown.isChecked()); save_button.setVisible(available)
        blocked_space.setVisible(not available or hide_countdown.isChecked())
        controls.setEnabled(not hide_countdown.isChecked()); preview_button.setEnabled(bool(current[0]) and not hide_countdown.isChecked() and not reason)
        value=draft()
        if current[0] and available and not initializing[0]:
            targets.set_profile(current[0],value)
        update_coordinates()
        update_colors()
        if current[0] and getattr(app,'_overlay_preview_game_id',None)==current[0]:
            app._overlay_game_preview_state=preview_state.currentData()
            from .budget import quota_plan
            app._overlay_preview_settings=targets.effective(quota_plan(candidate()),current[0]); app.update_overlay()
        error.hide()
    def choose(*args):
        if current[0] and getattr(app,'_overlay_preview_game_id',None)==current[0]:
            app._overlay_preview_game_id=None; app._overlay_preview_settings=None; app._overlay_preview_until=0; app.update_overlay()
        loading[0]=True; current[0]=games.currentData(); value=targets.profile(current[0])
        effective=replace(app.settings,**value)
        colors.clear(); colors.update((key,value[key]) for key in ('overlay_color_normal','overlay_color_warning') if key in value)
        hide_countdown.setChecked(not value.get('overlay_enabled',app.settings.overlay_enabled))
        wanted=effective.overlay_screen
        if wanted and monitor.findData(wanted)<0: monitor.addItem(t('{name} (not connected)',name=wanted),wanted)
        monitor.setCurrentIndex(max(0,monitor.findData(wanted))); picker.screen=choose_screen(wanted)
        picker.set_font_size(effective.overlay_font_size); picker.set_position(effective.overlay_x,effective.overlay_y); size.setValue(effective.overlay_font_size)
        opacity.setValue(round(effective.overlay_opacity*100))
        loading[0]=False; initializing[0]=True
        try: changed()
        finally: initializing[0]=False
        if picker.isVisible(): picker._background_controller.refresh()
    def coordinate(axis,value):
        point=list(picker.pixel_position()); point[axis]=int(value); picker.set_pixel_position(*point)
    for axis,edit in enumerate(coordinates): edit.valueChanged.connect(lambda value,n=axis:coordinate(n,value))
    def resize(value):
        if loading[0]: return
        position=list(picker.pixel_position()); anchors=(picker.x_ratio,picker.y_ratio); picker.set_font_size(int(value))
        for axis,ratio in enumerate(anchors):
            if ratio in (0,1): position[axis]=picker.pixel_limits()[axis][int(ratio)]
        picker.set_pixel_position(*position); changed()
    size.valueChanged.connect(resize)
    def screen_changed(*args):
        background=picker.game_background
        picker.screen=choose_screen(monitor.currentData() or '',background[1] if background else ''); picker.update(); changed()
    monitor.currentIndexChanged.connect(screen_changed); picker.positionChanged.connect(changed); hide_countdown.toggled.connect(changed)
    opacity.valueChanged.connect(changed)
    error=label('','danger'); error.setWordWrap(True); error.hide(); layout.addWidget(error)
    def update_colors():
        for kind,item in color_buttons.items():
            key='overlay_color_'+kind; color=colors.get(key,getattr(app.settings,key)); pixmap=QPixmap(18,18); pixmap.fill(QColor(color))
            if item.text()!=color.upper(): item.setIcon(QIcon(pixmap)); item.setText(color.upper())
        picker.text_color=colors.get('overlay_color_'+(preview_state.currentData() or 'warning'),getattr(app.settings,'overlay_color_'+(preview_state.currentData() or 'warning'))); picker.update()
    def choose_color(kind):
        key='overlay_color_'+kind; color=QColorDialog.getColor(QColor(colors.get(key,getattr(app.settings,key))),window,t('Choose countdown color'),QColorDialog.DontUseNativeDialog)
        if color.isValid(): colors[key]=color.name(); changed()
    def reset_colors():
        colors.update({key:getattr(app.settings,key) for key in ('overlay_color_normal','overlay_color_warning')}); changed()
    def change_consent():
        game=app.catalog.games.get(current[0])
        if not game: return
        try:
            accepted=app.overlay_consents.allows(game)
            if not accepted:
                from .game_safety import PROTECTED,UNCHECKED
                if safety.reason(game=game)!=PROTECTED or safety.inspection(game=game)==UNCHECKED: return
                from .qt_overlay_consent import request_consent
                if not request_consent(app,window,game): return
            app.overlay_consents.set(game,not accepted)
            app._overlay_preview_until=0; app._overlay_preview_target=None; app.hide_countdown()
            app.refresh_rtss_consent(); app.prepare_rtss_profiles(); changed()
            picker._background_controller.refresh()
            app.set_status('Overlay permission saved.' if not accepted else 'Overlay permission revoked.')
        except (ValueError,OSError,SQLiteError):
            error.setText(t('Could not save settings. Try again.')); error.show()
    def preview():
        app._overlay_preview_game_id=current[0]; app._overlay_game_preview_state=preview_state.currentData()
        settings=targets.effective(candidate(),current[0])
        status.setText(app.preview_counter_overlay(settings) if targets.rule(current[0]) else app.preview_game_overlay(settings))
    def change_minimize_consent():
        from .game_safety import PROTECTED,UNCHECKED
        game=app.catalog.games.get(current[0])
        if not game: return
        accepted=app.minimize_consents.allows(game)
        try:
            if not accepted:
                if safety.reason(game=game)!=PROTECTED or safety.inspection(game=game)==UNCHECKED: return
                from .qt_overlay_consent import request_consent
                if not request_consent(app,window,game,minimization=True): return
            app.minimize_consents.set(game,not accepted); app._restriction_grace=None; changed()
            app.set_status('Minimization permission revoked.' if accepted else 'Minimization permission saved.')
        except (ValueError,OSError,SQLiteError):
            error.setText(t('Could not save settings. Try again.')); error.show()
    def save():
        try:
            value=candidate(); app.store.save_settings(value); app.settings=app.catalog.settings=value
            targets.saved(value)
            app.prepare_rtss_profiles(); app.set_status('Countdown settings saved.'); window.accept()
            return True
        except (ValueError,OSError,SQLiteError) as exc:
            error.setText(t(str(exc)) if isinstance(exc,ValueError) else t('Could not save settings. Try again.')); error.show()
            return False
    preview_controls=QWidget(); preview_layout=QVBoxLayout(preview_controls); preview_layout.setContentsMargins(0,0,0,0); preview_layout.setSpacing(12)
    preview_layout.addWidget(separator()); preview_row=QHBoxLayout(); preview_button=button(t('Preview (10s)'),preview); preview_row.addWidget(preview_button)
    preview_row.addWidget(label(t('Preview state'),'muted')); preview_state=NoWheelComboBox(); preview_state.setAccessibleName(t('Preview state'))
    preview_state.addItem(t('Normal color'),'normal'); preview_state.addItem(t('Warning color'),'warning'); preview_state.setCurrentIndex(1)
    preview_state.currentIndexChanged.connect(changed); preview_row.addWidget(preview_state,1); preview_layout.addLayout(preview_row)
    status=label(t('Preview brings a running game to the foreground. Alt+Tab ends the preview.'),'muted'); status.setWordWrap(True); preview_layout.addWidget(status); layout.addWidget(preview_controls)
    actions=QHBoxLayout()
    actions.addStretch(); actions.addWidget(button(t('Cancel'),window.reject)); save_button=button(t('Save'),save,'primary'); actions.addWidget(save_button); layout.addLayout(actions)
    def finished(*args):
        if getattr(app,'_overlay_preview_game_id',None) in drafts or getattr(app,'_overlay_preview_game_id',None)==current[0]:
            app._overlay_preview_game_id=None; app._overlay_preview_settings=None; app._overlay_preview_until=0
            app._overlay_preview_target=None; app._overlay_game_preview_state=None
        app.update_overlay()
    def refresh_games():
        targets.refresh(); rows=targets.rows()
        if rows==[(games.itemText(i),games.itemData(i)) for i in range(games.count())]: return
        selected=games.currentData(); blocked=games.blockSignals(True)
        games.clear()
        for name,key in rows: games.addItem(name,key)
        games.setPlaceholderText(t('Choose a countdown.'))
        games.setCurrentIndex(max(0,games.findData(selected)) if rows else -1); games.blockSignals(blocked)
        choose(); save_button.setEnabled(bool(rows))
    window._refresh_games=refresh_games
    window.finished.connect(finished); games.currentIndexChanged.connect(choose); choose()
    save_button.setEnabled(games.count()>0); window.show(); dark_window(window)
