"""Native macOS windows and menus; image actions route through the editor registry."""
import functools
import json
import platform
import subprocess
import threading
import urllib.parse
from release import VERSION,TITLE

_windows={};_app=None;_url=None;_target=None;_build=None;_title_label=None
_maximize_state={'active':False,'frame':None}
# Standard macOS title bar height. These auxiliary windows are real titled windows
# (see open_window), so both their initial size and their content-driven auto-fit
# height need to add this on top of the content height, or the title bar eats into
# it and clips the bottom of the content.
NATIVE_CHROME=28

def refresh_menus():
    if _build:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(_build)

def toggle_maximize(app):
    """The app's "Full Screen" command. Uses window.maximize() (a plain frame
    resize) rather than toggle_fullscreen() (the Spaces-based transition, which
    doesn't correctly resize this window's content) -- see the FullScreenPrimary
    comment in build() below. maximize() is one-way, so the previous frame is
    remembered here to make this a real toggle, matching what "Full Screen" is
    everywhere else in the app (the menu item, its shortcut, the keyboard list)."""
    if not app.WINDOW:return
    if _maximize_state['active']:
        frame=_maximize_state['frame']
        if frame:
            app.WINDOW.resize(frame[2],frame[3])
            app.WINDOW.move(frame[0],frame[1])
        _maximize_state['active']=False
    else:
        _maximize_state['frame']=(app.WINDOW.x,app.WINDOW.y,app.WINDOW.width,app.WINDOW.height)
        app.WINDOW.maximize()
        _maximize_state['active']=True

@functools.lru_cache(maxsize=1)
def available_apps():
    if platform.system()!='Darwin': return {}
    result={}
    for key,names in {'photoshop':['Adobe Photoshop 2026','Adobe Photoshop 2025','Adobe Photoshop'],
                      'affinity':['Affinity','Affinity Photo 2','Affinity Photo'],'photos':['Photos']}.items():
        for name in names:
            if subprocess.run(['open','-Ra',name],capture_output=True).returncode==0: result[key]=name;break
    return result

def dispatch(command):
    if not _app or not _app.WINDOW:return
    if command in ('undo','redo','close-batch'):
        import AppKit as A
        front=A.NSApplication.sharedApplication().keyWindow()
        if front:
            for child in list(_windows.values()):
                if str(front.title())==child.title:
                    if command=='close-batch':child.destroy()
                    else:threading.Thread(target=lambda:child.evaluate_js('document.execCommand('+json.dumps(command)+')'),daemon=True).start()
                    return
    threading.Thread(target=lambda:_app.WINDOW.evaluate_js('window.claretteCommand('+json.dumps(command)+')'),daemon=True).start()

def open_window(app,kind,payload=None):
    import webview
    if kind not in ('settings','shortcuts','help','new-batch','rename-batch','export','preset','workspace','updates'):raise ValueError('Unknown window')
    query=urllib.parse.urlencode(dict(kind=kind,**(payload or {})))
    url=(_url or 'http://127.0.0.1:'+str(app.SERVER.server_address[1]))+'/window.html?'+query
    if not app.WINDOW:return {'url':url}
    if kind in _windows:
        try:_windows[kind].show();_windows[kind].restore();return {'ok':True}
        except Exception:
            try:_windows[kind].destroy()
            except Exception:pass
            _windows.pop(kind,None)
    sizes={'settings':(900,760),'shortcuts':(760,680),'help':(680,600),'export':(490,490),'preset':(400,330),'rename-batch':(400,118),'new-batch':(460,220),'workspace':(400,220),'updates':(520,260)}
    width,height=sizes.get(kind,(440,320))
    titles={'settings':'Settings','shortcuts':'Keyboard Shortcuts','help':'Documentation & Tutorials','new-batch':'New Batch','rename-batch':'Rename Batch','export':'Export Finals','preset':'Output Preset','workspace':'Workspace','updates':'Check for Updates'}
    # frameless=False (a real, native title bar) is deliberate: see the comment in
    # configure_floating below for why. easy_drag only matters when frameless=True.
    # height includes an extra NATIVE_CHROME for the native title bar itself (see
    # fit_window below for why that's needed).
    window=webview.create_window(titles.get(kind,kind.replace('-',' ').title()),url,width=width,height=height+NATIVE_CHROME,min_size=(width,100),resizable=False,frameless=False,background_color='#20232d',on_top=False)
    configured={'done':False}
    def configure_floating():
        # Reusing a window (show()/restore()) re-fires the 'shown' event this is bound
        # to, which was re-running this whole native setup every time -- redundant, and
        # if it lands while the window is being interacted with it looks like a glitch.
        # Apply it once per window, not once per show.
        if platform.system()!='Darwin' or configured['done']:return
        from PyObjCTools import AppHelper
        def apply():
            if configured['done']:return
            configured['done']=True
            import AppKit as A
            from webview.platforms.cocoa import BrowserView
            instance=BrowserView.instances.get(window.uid)
            if not instance:return
            native=instance.window
            # A real (if invisible) native title bar, same trick already used for the
            # main window: this makes dragging a plain, free, zero-lag OS-level window
            # move -- there is no per-event JS/Cocoa emulation to be slow, the same as
            # every other native Mac window (Photoshop and Zoom's own floating panels
            # work this way, not via a fully custom frameless window). It also keeps the
            # system's own rounded window corners, so no layer masking is needed either.
            native.setStyleMask_(native.styleMask() & ~A.NSWindowStyleMaskMiniaturizable & ~A.NSWindowStyleMaskResizable)
            # Regular native title (shows which window this is) and the regular red
            # close button -- no custom in-page close control, that would just be a
            # second one. Miniaturize/zoom stay hidden; these windows don't support
            # either.
            for role in (A.NSWindowMiniaturizeButton,A.NSWindowZoomButton):
                button=native.standardWindowButton_(role)
                if button:button.setHidden_(True)
            native.setLevel_(A.NSFloatingWindowLevel)
        AppHelper.callAfter(apply)
    window.events.shown+=configure_floating
    _windows[kind]=window
    window.events.closed+=lambda:_windows.pop(kind,None)
    return {'ok':True}

def close_window(kind):
    window=_windows.get(kind)
    if window:window.destroy()

def close_auxiliary_windows():
    # Main-window close must not leave Settings or Export keeping Cocoa alive.
    for window in list(_windows.values()):
        window.destroy()


def install(app,url):
    global _app,_url,_target,_build
    _app=app;_url=url
    if platform.system()!='Darwin':return
    from PyObjCTools import AppHelper
    import AppKit as A
    # Clarette has no use for multi-tab windows; without this, macOS auto-inserts
    # "Show Tab Bar" / "Show All Tabs" into the View menu on its own.
    A.NSWindow.setAllowsAutomaticWindowTabbing_(False)
    from webview.platforms.cocoa import BrowserView
    class MenuTarget(A.NSObject):
        def performCommand_(self,sender):dispatch(str(sender.representedObject()))
    _target=MenuTarget.alloc().init()
    def build():
        global _title_label
        main=A.NSMenu.alloc().init()
        def menu(title):
            top=A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title,None,'');sub=A.NSMenu.alloc().initWithTitle_(title);top.setSubmenu_(sub);main.addItem_(top);return sub
        def item(m,title,command=None,selector=None,key='',symbol=None):
            if title=='-':m.addItem_(A.NSMenuItem.separatorItem());return
            # command-routed items (performCommand: -> dispatch() -> evaluate_js
            # 'window.claretteCommand(...)') must NOT also carry a live AppKit key
            # equivalent for that same shortcut: commands.js's own keydown listener
            # in the webview already matches the identical shortcut and calls
            # claretteCommand directly, so a real key equivalent here doesn't
            # replace that path, it races it -- both firing for one keypress,
            # each starting its own job and posting its own completion
            # notification (the "duplicate notification" bug). The menu item
            # stays fully clickable either way; it just no longer duplicates the
            # keyboard path. Only explicit selector= items (Cut/Copy/Paste/Hide/
            # Quit, real one-off AppKit actions with no JS-side listener) still
            # get a live key equivalent, via their own literal key= argument.
            mods=A.NSCommandKeyMask
            entry=A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title,selector or 'performCommand:',key if selector else '')
            entry.setKeyEquivalentModifierMask_(mods)
            if command:entry.setTarget_(_target);entry.setRepresentedObject_(command)
            if symbol and hasattr(A.NSImage,'imageWithSystemSymbolName_accessibilityDescription_'):
                image=A.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol,title)
                if image:entry.setImage_(image)
            m.addItem_(entry);return entry
        appmenu=menu('Clarette');item(appmenu,'Settings…','settings');item(appmenu,'Check for Updates…','updates');item(appmenu,'-')
        services=item(appmenu,'Services',selector=None);services.setTarget_(None);services.setAction_(None);service_menu=A.NSMenu.alloc().init();services.setSubmenu_(service_menu);A.NSApplication.sharedApplication().setServicesMenu_(service_menu)
        item(appmenu,'Hide Clarette',selector='hide:',key='h');hide=item(appmenu,'Hide Others',selector='hideOtherApplications:',key='h');hide.setKeyEquivalentModifierMask_(A.NSCommandKeyMask|A.NSAlternateKeyMask)
        item(appmenu,'Show All',selector='unhideAllApplications:');item(appmenu,'-');item(appmenu,'Quit Clarette',selector='terminate:',key='q')
        file=menu('File')
        for title,cmd in [('New Batch…','new-batch'),('Close Batch','close-batch'),('-',''),('Add Images…','import'),('Import ZIP…','import-zip'),('Clear Images','clear'),('-',''),('Rename Batch…','rename-batch'),('Change Batch Output Folder…','batch-folder'),('Reveal Batch Output Folder','final'),('Open Work Folder','working')]:item(file,title,cmd)
        color=item(file,'Output Color Profile');color.setTarget_(None);color.setAction_(None);sub=A.NSMenu.alloc().initWithTitle_('Output Color Profile');color.setSubmenu_(sub);item(sub,'RGB - Digital','rgb');item(sub,'CMYK - Print','cmyk');item(file,'-');item(file,'Export Finals','export')
        edit=menu('Edit')
        for title,cmd in [('Undo','undo'),('Redo','redo'),('-',''),('Auto Fit to Guide','auto-fit'),('Auto Color','auto-color'),('Enhance','enhance')]:item(edit,title,cmd)
        item(edit,'-')
        for title,selector,key in [('Cut','cut:','x'),('Copy','copy:','c'),('Paste','paste:','v'),('Select All','selectAll:','a')]:item(edit,title,selector=selector,key=key)
        view=menu('View')
        # Original/Current Comparison and Preview Color Changes are toolbar-only actions,
        # not global view state, so they don't belong in this menu.
        for title,cmd,symbol in [('Show Transparency','transparency','checkerboard.rectangle'),('Show Solid Preview Background','solid','square.fill'),('Show/Hide Guides','guides','ruler'),('Fit to Output','fit','arrow.up.left.and.arrow.down.right')]:item(view,title,cmd,symbol=symbol)
        # The main window no longer advertises native fullscreen support at all (see
        # the FullScreenPrimary comment in build() above), so macOS has nothing to
        # auto-insert here -- this is the only "Enter Full Screen" item that exists.
        item(view,'Entire Screen','fullscreen')
        workspace=menu('Workspace')
        for title,cmd in [('Landscape Mode','workspace-landscape'),('Portrait Mode','workspace-portrait'),('-',''),
                          ('New Workspace…','workspace-new'),('Rename Workspace…','workspace-rename'),('Delete Workspace…','workspace-delete'),('-',''),
                          ('Save Workspace Layout','workspace-save'),('Reset Current Workspace','workspace-reset'),('Restore Default Layout','workspace-restore-default'),('-',''),
                          ('Unlock Workspace' if app.S['workspace2'].get('locked') else 'Lock Workspace','workspace-lock')]:item(workspace,title,cmd)
        helpmenu=menu('Help')
        for title,cmd in [('Documentation & Tutorials','help'),('Keyboard Shortcuts…','shortcuts'),('Send Feedback…','feedback')]:item(helpmenu,title,cmd)
        A.NSApplication.sharedApplication().setMainMenu_(main);A.NSApplication.sharedApplication().setHelpMenu_(helpmenu)
        instance=BrowserView.instances.get(app.WINDOW.uid)
        if instance:
            window=instance.window
            # Restore the standard centered NSWindow title, not a toolbar title label.
            window.setTitleVisibility_(A.NSWindowTitleVisible)
            window.setTitlebarAppearsTransparent_(False)
            window.setStyleMask_(window.styleMask() & ~A.NSWindowStyleMaskFullSizeContentView)
            # True native fullscreen (the Spaces-based transition) doesn't correctly
            # resize this window's content, unlike a plain resize/maximize -- so this
            # window doesn't advertise support for it at all. Our own "Enter Full
            # Screen" command uses window.maximize() instead (a plain frame resize,
            # same mechanism as a manual drag-resize), and with FullScreenPrimary
            # cleared here, macOS won't offer or auto-insert its own broken version
            # via the green button or the View menu.
            window.setCollectionBehavior_(window.collectionBehavior() & ~(1<<7))
            window.setTitle_(TITLE)
            # macOS 26 left-aligns even a standard title. A symmetric native label
            # keeps the title visually centered as the frame resizes.
            window.setTitleVisibility_(A.NSWindowTitleHidden)
            frame=window.contentView().superview()
            if _title_label is None:
                _title_label=A.NSTextField.alloc().initWithFrame_(A.NSMakeRect(90,frame.bounds().size.height-27,frame.bounds().size.width-180,22))
                _title_label.setStringValue_(TITLE);_title_label.setEditable_(False);_title_label.setSelectable_(False)
                _title_label.setBordered_(False);_title_label.setDrawsBackground_(False);_title_label.setAlignment_(A.NSTextAlignmentCenter)
                _title_label.setFont_(A.NSFont.systemFontOfSize_(12));_title_label.setTextColor_(A.NSColor.secondaryLabelColor())
                _title_label.setAutoresizingMask_(A.NSViewWidthSizable|A.NSViewMinYMargin);frame.addSubview_(_title_label)
    _build=build
    AppHelper.callAfter(build)


def fit_window(kind,height):
    if kind in ('settings','shortcuts','help'):return
    window=_windows.get(kind)
    if window:window.resize(window.width,max(100,min(900,int(height)+NATIVE_CHROME)))
