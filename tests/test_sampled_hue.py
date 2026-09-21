import sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import imaging

class SampledHueTests(unittest.TestCase):
 def test_red_wrap_and_feather(self):
  h=np.array([300,315,330,345,0,15,30,45,60])
  np.testing.assert_allclose(imaging._hue_weight(h,0,[-45,-15,15,45]),[0,0,.5,1,1,1,.5,0,0])
 def test_asymmetric_range(self):
  np.testing.assert_allclose(imaging._hue_weight(np.array([80,90,100,110,120,140]),100,[-20,-10,10,40]),[0,1,1,1,2/3,0])
 def test_legacy_range_unchanged(self):
  np.testing.assert_allclose(imaging._hue_weight(np.array([0,30,60,330]),0),[1,.5,0,.5])
 def test_validation_and_roundtrip(self):
  c=imaging.settings({'color_ranges':{'red':{'center':365,'bounds':[-45,-15,15,45],'hue':50}}})
  self.assertEqual(c['color_ranges']['red']['center'],5)
  self.assertEqual(imaging.settings(c),c)
  for bounds in [[10,0,20,40],[-181,-15,15,45],[0,1,2],[0,1,2,float('nan')]]:
   with self.assertRaises(ValueError):imaging.settings({'color_ranges':{'red':{'bounds':bounds}}})
 def test_export_pixels_protect_other_hues_and_alpha(self):
  im=Image.new('RGBA',(3,1));im.putdata([(255,0,0,100),(0,255,0,200),(0,0,255,255)])
  c={'color_ranges':{'red':{'center':0,'bounds':[-45,-15,15,45],'hue':60}}}
  out=imaging.color(im,c)
  self.assertEqual(list(out.getchannel('A').getdata()),[100,200,255])
  np.testing.assert_allclose(np.array(out)[0,:,:3],[[255,255,0],[0,255,0],[0,0,255]],atol=1)
