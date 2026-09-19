"""Local notifications sent by Clarette's own application bundle."""
import sys,uuid,logging,subprocess
from pathlib import Path
_center=None
_delegate=None

def initialize():
    global _center,_delegate
    if sys.platform!='darwin' or not getattr(sys,'frozen',False):return False
    if _center is not None:return True
    try:
        import UserNotifications as UN
        import objc
        from Foundation import NSObject
        class ClaretteNotificationDelegate(NSObject, protocols=[objc.protocolNamed("UNUserNotificationCenterDelegate")]):
            def userNotificationCenter_willPresentNotification_withCompletionHandler_(self,center,notification,completion):
                options=UN.UNNotificationPresentationOptionBanner|UN.UNNotificationPresentationOptionList
                if notification.request().content().sound() is not None:options|=UN.UNNotificationPresentationOptionSound
                completion(options)
        _delegate=ClaretteNotificationDelegate.alloc().init()
        _center=UN.UNUserNotificationCenter.currentNotificationCenter()
        _center.setDelegate_(_delegate)
        return True
    except Exception:
        logging.exception('Clarette notifications unavailable');return False

def play_sound():
    """Wait for the system player, so unavailable audio is reported as a failure."""
    if sys.platform!='darwin':return False
    try:
        from Foundation import NSUserDefaults
        configured=NSUserDefaults.standardUserDefaults().stringForKey_('com.apple.sound.beep.sound')
        sound=Path(configured) if configured else Path('/System/Library/Sounds/Glass.aiff')
        if not sound.is_file():sound=Path('/System/Library/Sounds/Glass.aiff')
        result=subprocess.run(['/usr/bin/afplay',str(sound)],capture_output=True,text=True,timeout=10)
        if result.returncode:
            logging.warning('Clarette audio playback failed: %s',result.stderr.strip())
            return False
        return True
    except Exception:
        logging.exception('Clarette notification sound unavailable');return False

def send(message,sound=False):
    played=play_sound() if sound else False
    if not initialize():return {'native':False,'sound_played':played}
    import UserNotifications as UN
    content=UN.UNMutableNotificationContent.alloc().init();content.setTitle_('Clarette');content.setBody_(message)
    # Sound is played directly once, so a denied/suppressed banner cannot swallow it.
    request=UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(str(uuid.uuid4()),content,None)
    def authorized(granted,error):
        if granted:_center.addNotificationRequest_withCompletionHandler_(request,lambda error: logging.warning('Notification delivery failed: %s',error) if error else None)
        else:logging.warning('Clarette banner permission was not granted: %s',error)
    _center.requestAuthorizationWithOptions_completionHandler_(UN.UNAuthorizationOptionAlert|UN.UNAuthorizationOptionSound,authorized)
    return {'native':True,'sound_played':played}
