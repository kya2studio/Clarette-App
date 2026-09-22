import os,sys,tempfile,unittest,json,time
from pathlib import Path
from unittest.mock import patch
os.environ['CLARETTE_DATA']=tempfile.mkdtemp(prefix='clarette-regression-')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,preferences,imaging,storage
import numpy as np
from PIL import Image

def layout():
 return {'grid':{'root':{'type':'leaf','data':{'views':['preview'],'activeView':'preview'},'size':100},'width':100,'height':100,'orientation':'HORIZONTAL'},'panels':{'preview':{'id':'preview','contentComponent':'section'}}}

class SessionFixTests(unittest.TestCase):
 def setUp(self):app.S=app.fresh();app.JOBS.clear()
 def import_portrait(self):
  app.import_items([('test.png',imaging.png(Image.new('RGBA',(40,50),'blue')))],'Test')
  return app.S['batches'][app.S['active']]['files'][0]
 def test_autosave_never_creates_saved_workspace(self):
  for _ in range(5):app.action('/api/workspace',{'operation':'autosave','id':'landscape','layout':layout()})
  self.assertEqual(app.S['workspace2']['custom'],{})
  self.assertEqual(preferences.recover_workspace2(app.S['workspace2'])[0]['autosaved']['landscape'],layout())
 def test_old_auto_forks_migrate_but_explicit_workspaces_survive(self):
  custom={str(i):dict(name='Custom Layout',layout=layout(),basedOn='portrait') for i in range(8)}
  custom['named']=dict(name='Custom Layout',layout=layout(),basedOn='portrait',explicit=True)
  ws=preferences.validate_workspace2(dict(active='7',custom=custom))
  self.assertEqual(list(ws['custom']),['named']);self.assertEqual(ws['active'],'portrait');self.assertEqual(ws['autosaved']['portrait'],layout())
 def test_clear_purges_owned_files_history_and_legacy_not_exports(self):
  f=self.import_portrait();bid=f['batch'];owned=app.folder(f)
  legacy=app.DATA/'batches'/bid;legacy.mkdir(parents=True,exist_ok=True);(legacy/'copy.png').write_bytes(b'copy')
  exported=app.DATA/'final-output.png';exported.write_bytes(b'export')
  app.action('/api/remove-portrait',dict(batch=bid,id=f['id']))
  app.action('/api/clear-batch',{'confirm_unsaved':True})
  self.assertFalse(owned.exists());self.assertFalse(legacy.exists());self.assertFalse(app.S['batches'][bid]['removed_files']);self.assertEqual(exported.read_bytes(),b'export')
 def test_new_batch_clears_previous_only_after_valid_name(self):
  f=self.import_portrait();owned=app.folder(f);bid=f['batch']
  with self.assertRaises(ValueError):app.action('/api/new-batch',{'name':'../bad'})
  self.assertTrue(owned.exists());self.assertEqual(app.S['active'],bid)
  app.action('/api/new-batch',{'name':'Next','output':str(app.DATA/'exports')})
  self.assertFalse(owned.exists());self.assertNotIn(bid,app.S['batches'])
 def test_cleanup_rejects_symlink(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'batches').mkdir();outside=root/'outside';outside.mkdir();(outside/'keep').write_text('keep');(root/'batches'/'one').symlink_to(outside,target_is_directory=True)
   with self.assertRaises(ValueError):storage.discard_batch(root,root/'data','one')
   self.assertTrue((outside/'keep').exists())
 def test_transparent_refine_preserves_alpha_and_solid_pixels(self):
  a=np.zeros((20,20),dtype=np.uint8);a[4:16,4:16]=255;a[3,4:16]=100
  im=Image.new('RGBA',(20,20),(80,60,40,255));im.putalpha(Image.fromarray(a))
  rgb,m=imaging.refine_transparent(im,Image.fromarray(a))
  np.testing.assert_array_equal(np.asarray(m),a);self.assertEqual(rgb.getpixel((8,8)),(80,60,40,255))
 def test_repeat_detection_reuses_result_without_model_or_recoloring(self):
  f=self.import_portrait();name='MASKS/detected.png';app.atomic(app.folder(f)/name,imaging.png(Image.new('L',(40,50),180)))
  f['detection']={'stamp':f['work_stamp'],'model':app.S['settings']['model'],'quality':True,'mask':name}
  before=app.source(f).tobytes()
  with patch.object(app.ENGINE,'call',side_effect=AssertionError('Model must not run for unchanged pixels')):
   jid=app.action('/api/mask-detect',dict(batch=f['batch'],id=f['id']))['job']
   deadline=time.monotonic()+5
   while app.JOBS[jid]['status']=='running' and time.monotonic()<deadline:time.sleep(.01)
   self.assertEqual(app.JOBS[jid]['status'],'done',app.JOBS[jid])
  self.assertEqual(app.source(f).tobytes(),before);self.assertEqual(app.mask(f).getextrema(),(180,180))
 def test_detection_restores_original_background_for_transparent_enhancement(self):
  f=self.import_portrait();working=app.source(f);working.putalpha(200);app.commit_work(f,working)
  def worker(request,report):
   self.assertEqual(imaging.load(request['source']).getchannel('A').getextrema(),(255,255))
   dest=Path(request['output'])/'mask.png';Image.new('L',(40,50),180).save(dest)
   return {'mask':str(dest)}
  with patch.object(app.ENGINE,'call',side_effect=worker):
   jid=app.action('/api/mask-detect',dict(batch=f['batch'],id=f['id']))['job']
   deadline=time.monotonic()+5
   while app.JOBS[jid]['status']=='running' and time.monotonic()<deadline:time.sleep(.01)
   self.assertEqual(app.JOBS[jid]['status'],'done',app.JOBS[jid])
 def test_completion_sound_waits_for_presentation_and_is_idempotent(self):
  from unittest.mock import Mock
  sound=Mock();app.S['settings']['notification_sound']=True
  app.JOBS['test']={'id':'test','status':'running'}
  with patch.object(app,'WINDOW',object()),patch('notifications.play_sound',sound):
   app.action('/api/job-presented',{'job':'test'});self.assertFalse(sound.called)
   app.JOBS['test']['status']='done'
   app.action('/api/job-presented',{'job':'test'});app.action('/api/job-presented',{'job':'test'})
   deadline=time.monotonic()+1
   while not sound.called and time.monotonic()<deadline:time.sleep(.01)
   sound.assert_called_once()
 def test_completion_banner_never_plays_early_audio(self):
  app.S['settings'].update(notifications=True,notification_sound=True)
  with patch.object(app,'WINDOW',object()),patch('notifications.send') as send:
   app.notify('Auto Color complete');send.assert_called_once_with('Auto Color complete',sound=False)
 def test_toolbar_defaults_and_validation(self):
  self.assertEqual(preferences.defaults()['toolbar_tools'],['chatgpt','gemini','prompt'])
  self.assertEqual(preferences.validate_settings({'toolbar_tools':[]})['toolbar_tools'],[])
  with self.assertRaises(ValueError):preferences.validate_settings({'toolbar_tools':['settings']})
if __name__=='__main__':unittest.main()
