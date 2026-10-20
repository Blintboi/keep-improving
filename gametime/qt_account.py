"""Account and connection-code controls; background I/O belongs to AuthWorker."""
from dataclasses import replace
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QCheckBox,QLineEdit,QApplication,QMessageBox
from shiboken6 import isValid
from .qt_widgets import label,button
from .statistics_sync import group_code,display_code,computer_name
from .statistics_cloud import CLOUD_CODE,new_code
from .statistics_auth import MESSAGES


def statistics_dialog(app):
    # Imported here to retain the controller's configurable/test service URL.
    from .qt_ui import CodeVisibilityGuard,dark_window
    t=app.t; window=app._dialog(t('Link computers'),760)
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(14)
    layout.addWidget(label(t('Link computers'),'section'))
    note=label(t('Sign in with GitHub to create or manage a connection code. To link another computer, enter the same existing code.'))
    note.setWordWrap(True); layout.addWidget(note)
    account_row=QHBoxLayout(); account=label('','muted'); account.setTextFormat(Qt.PlainText); account_row.addWidget(account,1)
    login=button(t('Sign in with GitHub'),lambda:authenticate('login'))
    logout=button(t('Sign out'),lambda:authenticate('logout'))
    account_row.addWidget(login); account_row.addWidget(logout); layout.addLayout(account_row)
    enabled=QCheckBox(t('Automatically synchronize statistics')); enabled.setChecked(app.settings.statistics_sync_enabled or not CLOUD_CODE.fullmatch(app.settings.statistics_sync_group)); layout.addWidget(enabled)
    layout.addWidget(label(t('Computer name'),'muted'))
    name=QLineEdit(app.settings.statistics_device_name or computer_name()); name.setMaxLength(80); name.setMinimumHeight(40); name.setAccessibleName(t('Computer name')); layout.addWidget(name)
    layout.addWidget(label(t('Connection code'),'muted'))
    pending=app.store.pending_connection()
    existing=app.settings.statistics_sync_group
    generated=[pending or (existing if CLOUD_CODE.fullmatch(existing) else new_code())]
    requires_login=[bool(pending or not CLOUD_CODE.fullmatch(existing))]
    code_row=QHBoxLayout(); code=QLineEdit(display_code(generated[0])); code.setMaxLength(40); code.setMinimumHeight(40); code.setAccessibleName(t('Connection code')); code_row.addWidget(code,1)
    code.setEchoMode(QLineEdit.Password); code.setStyleSheet('font-family:Consolas; font-size:14px;')
    reveal=button(t('Show code'),lambda:None); reveal.setCheckable(True)
    reveal.setToolTip(t('The code is hidden again when you leave this window.'))
    def visibility(visible):
        code.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        reveal.setText(t('Hide code' if visible else 'Show code'))
    reveal.toggled.connect(visibility); code_row.addWidget(reveal)
    window._code_visibility_guard=CodeVisibilityGuard(window,lambda:reveal.setChecked(False))
    def regenerate():
        reveal.setChecked(False); generated[0]=new_code(); requires_login[0]=True
        code.setText(display_code(generated[0]))
    new=button(t('New code'),regenerate); code_row.addWidget(new)
    code_row.addWidget(button(t('Copy'),lambda:QApplication.clipboard().setText(code.text()))); layout.addLayout(code_row)
    secret=label(t('Keep your code private: anyone with it can link a computer. Replacing your managed code disconnects its other computers.'),'muted'); secret.setWordWrap(True); layout.addWidget(secret)
    help_text=label(t('Only statistics are shared. Daily limits, exclusions, executable paths and settings stay on each computer.'),'muted'); help_text.setWordWrap(True); layout.addWidget(help_text)
    error=label('','danger'); error.setWordWrap(True); layout.addWidget(error)
    def update():
        if not isValid(window): return
        session=app.account_session
        account.setText(t('Signed in: {name}',name=session['name'] or 'GitHub') if session else t('Not signed in'))
        login.setVisible(not bool(session)); logout.setVisible(bool(session)); revoke.setVisible(bool(session))
        for widget in (login,logout,revoke,save_button,enabled,name,code,new): widget.setEnabled(not app._auth_busy)
    window._account_update=update
    def authenticate(action):
        error.setText(t('Opening GitHub sign-in…') if action=='login' else '')
        app.request_account(action,'',lambda value,warning:finished_auth(warning))
        update()
    def finished_auth(warning):
        if isValid(window): error.setText(t(warning)); update()
    def commit(settings):
        # Other settings can change while the account request runs in background.
        settings=replace(app.settings,statistics_sync_enabled=settings.statistics_sync_enabled,
            statistics_sync_group=settings.statistics_sync_group,statistics_device_name=settings.statistics_device_name).validate()
        app.store.save_settings(settings); app.settings=app.catalog.settings=settings
        app.store.pending_connection(clear=True)
        app.statistics_sync.cancel(); app._sync_busy=False; app._sync_attempted=0
        app._sync_interval=60; app._sync_revision=None
        app._sync_status='Statistics sync is off.'; app.statistics.scope='all'; app.statistics.refresh()
        app.request_statistics_sync(); app.update_statistics_sync_status(); window.accept()
    def provision(settings,action='activate'):
        if app._auth_busy: return
        app.store.pending_connection(settings.statistics_sync_group)
        def finished(value,warning):
            if not isValid(window): return
            update()
            if value.get('ok'):
                try: commit(settings)
                except (OSError,ValueError,SQLiteError): error.setText(t('Could not save connection settings. Try again.'))
            elif value.get('error')=='other_group':
                question=t('Replace your cloud connection code? Copies on the server for the previous code will be removed. Your local history stays available. Enter the new code again on your other computers.')
                if QMessageBox.question(window,t('Replace connection code'),question,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
                    provision(settings,'rotate')
                else: error.setText(t(MESSAGES['other_group']))
            else: error.setText(t(warning or MESSAGES['unavailable']))
        app.request_account(action,settings.statistics_sync_group,finished); update()
    def save():
        from .qt_ui import SERVICE_URL
        if app._auth_busy: return
        try:
            if enabled.isChecked() and not SERVICE_URL: raise ValueError('The synchronization service is not configured yet.')
            settings=replace(app.settings,statistics_sync_enabled=enabled.isChecked(),statistics_sync_group=group_code(code.text()),statistics_device_name=name.text().strip()).validate()
            if settings.statistics_sync_enabled and app.account_session:
                provision(settings)
            elif settings.statistics_sync_enabled and requires_login[0] and settings.statistics_sync_group==generated[0]:
                error.setText(t(MESSAGES['session']))
            else: commit(settings)
        except (OSError,ValueError) as exc: error.setText(t(str(exc)))
        except SQLiteError: error.setText(t('Could not save connection settings. Try again.'))
    def revoke_group():
        question=t('Revoke your managed connection code and remove its server copies? Local history is kept. All computers using that code will stop synchronizing.')
        if QMessageBox.question(window,t('Revoke cloud connection'),question,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        def finished(value,warning):
            if not isValid(window): return
            update(); error.setText(t('Cloud connection revoked. Local history is kept.') if value.get('ok') else t(warning))
        app.request_account('revoke','',finished); update()
    actions=QHBoxLayout(); revoke=button(t('Revoke cloud connection'),revoke_group); actions.addWidget(revoke); actions.addStretch()
    actions.addWidget(button(t('Cancel'),window.reject)); save_button=button(t('Save'),save,'primary'); actions.addWidget(save_button); layout.addLayout(actions)
    update(); window.show(); dark_window(window)
