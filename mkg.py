#!/usr/bin/python -Ou
# Parasite on Crosser's mkgallery2 (http://www.average.org/mkgallery/) perl script.
Script = 'mkg.py'

import sys, getopt, os, logging, time, exceptions, imghdr

g2dir = '.gallery2'
output = 'i.html'
sizes = (160, 640, 1600)
subdirs = ['.html'] + ['.'+str(x) for x in sizes]
html_templates = (
    '.html/%(curr_img)s-info.html',
    '.html/%(curr_img)s-slide.html',
    '.html/%(curr_img)s-static.html',
)
prereq = (
    'gallery.css',
    'custom.css',
	'mootools.js',
	'overlay.js',
	'urlparser.js',
	'multibox.js',
	'showwin.js',
	'controls.js',
	'show.js',
	'gallery.js',
)
header_pl = 'header.pl'
footer_pl = 'footer.pl'
header_py = 'header.py'
footer_py = 'footer.py'
image_types = (
  '.jpeg', '.jpg',
)

__HTML_header = '''<!DOCTYPE html
	PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
	 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US" xml:lang="en-US">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>%(title)s</title>
%(prereq)s
</head>
<body>

<!-- Created by %(version)s -->
<div class="indexContainer" id="indexContainer">
<h1 class="title">%(title)s</h1>
%(plugin_header)s
<h2 class="ititle">Images  <a class="showStart" rel="i%(first_img)s" href=".html/%(first_img)s-slide.html">&gt; slideshow</a></h2>
'''

__HTML_footer = '''
<br clear="all" /><hr />

</div>
%(plugin_footer)s
</body>
</html>
'''

__HTML_body = '''
<table id="%(curr_img)s" class="slide"><tr><td><div class="slidetitle">
<a class="infoBox"
 title="Image Info: %(curr_img)s"
 href=".html/%(curr_img)s-info.html"
>%(curr_img)s</a> 
</div>
<div class="slideimage">%(map_ref)s<a class="showImage"
 title="%(curr_img)s"
 rel="i%(curr_img)s"
 href=".html/%(curr_img)s-static.html"
><img
 class="thumbnail"
 src=".160/%(curr_img)s" alt="%(curr_img)s"
/></a></div><div class="varimages"
 title="%(curr_img)s"
 id="i%(curr_img)s">
<a class="conceal" title="Reduced to 160x120" rel="%(tn160)s"
 href=".160/%(curr_img)s">%(tn160)s</a> 
<a class="conceal" title="Reduced to 640x480" rel="%(tn640)s"
 href=".640/%(curr_img)s">%(tn640)s</a> 
<a class="conceal" title="Reduced to 1600x1200" rel="%(tn1600)s"
 href=".1600/%(curr_img)s">%(tn1600)s</a> 
<a title="Original" rel="%(curr_width)sx%(curr_height)s"
 href="%(curr_img)s">%(curr_width)sx%(curr_height)s</a>
</div></td></tr></table>
'''

RefreshOnly = False

ImageMagick_cli = False
ExifTran_cli = False

#  http://effbot.org/imagingbook/pil-index.htm
PIL_ok = True
try:
  from PIL import Image
  from PIL.ExifTags import TAGS, GPSTAGS
except ImportError,e:
  PIL_ok = False
  logging.error('PIL.Image ImportError %s',e)
else:
  PIL_ok = True
  # logging.critical('PIL.Image imported ok.')


PyExiv2_ok = True
try:
  import pyexiv2
except ImportError,e:
  PyExiv2_ok = False
  logging.error('PyExiv2 ImportError %s',e)
else:
  PyExiv2_ok = True
  # logging.critical('PyExiv2 imported ok.')

gExiv2_ok = True
try:
  from gi.repository import GExiv2
except ImportError,e:
  gExiv2_ok = False
  logging.error('gExiv2 ImportError %s',e)
else:
  gExiv2_ok = True
  # logging.critical('gExiv2 imported ok.')

def get_exif(name,context):
  pass

def resize_image(name,size,context):
  if RefreshOnly :
    return
  output = '.%d/%s' % (size,name)
  if PIL_ok :
    logging.debug("Using PIL to '%s' -> '%s'...",name,output)
    img = Image.open(name)
    x, y = context['image_sizes'][name] = img.size
    h_size, v_size = size, (size * 3) / 4 
    if x < y :
      h_size, v_size = v_size, h_size # swap'em
    img.resize((h_size,v_size),Image.ANTIALIAS).save(output,'JPEG')
  elif ImageMagick_cli :
    logging.debug("Using ImageMagick to '%s' -> '%s'...",name,output)
    copy(name,output)
    cmd = 'mogrify -resize %dx%d %s' % (size,size,output)
    logging.debug("++ Command was: %s",cmd)
    fp = os.popen(cmd,'r')
    o = fp.read()
    fp.close()
    logging.debug("++ Output was: %s",' '.join(o.split()))
  else:
    logging.fatal("Cannot process images - no backend.")
    sys.exit(2)

def zapz(s):
  if (type(s) == type('x')) :
    if (s == '\0'*len(s)) :
      return 'Z%dZ'%(len(s),)
  return `s`

def _cvt2degress(value):
  d0, d1 = value[0] ; d = float(d0) / float(d1)
  m0, m1 = value[1] ; m = float(m0) / float(m1)
  s0, s1 = value[2] ; s = float(s0) / float(s1)
  return d + (m / 60.0) + (s / 3600.0)

def image_size(name,context):
  try:
    return context['image_sizes'][name]
  except KeyError:
    pass
  if PIL_ok :
    logging.debug("Using PIL to read '%s'.",name)
    img = Image.open(name)
    context['image_sizes'][name] = img.size
    #
    # hack. extract EXIF here...
    exif = img._getexif()
    d = {}
    logging.debug('EXIF(%s): BEGIN',name)
    for tag, value in exif.items():
      decoded = TAGS.get(tag,tag)
      if decoded == 'MakerNote' :
        continue
      if decoded == 'GPSInfo' :
        # https://gist.github.com/erans/983821
        gps_data = {}
        for t in value :
          dd = GPSTAGS.get(t,t)
          gps_data[dd] = value[t]
        gps_lat_val = gps_data.get('GPSLatitude',None)
        if gps_lat_val is not None :
          gps_lat_ref = gps_data.get('GPSLatitudeRef',None)
          gps_lat = _cvt2degress(gps_lat_val)
          if gps_lat_ref != 'N' :
            gps_lat = 0.0 - gps_lat
          d['GPS-Latitude'] = gps_lat
        gps_lon_val = gps_data.get('GPSLongitude',None)
        if gps_lon_val is not None :
          gps_lon_ref = gps_data.get('GPSLongitudeRef',None)
          gps_lon = _cvt2degress(gps_lon_val)
          if gps_lon_ref != 'E' :
            gps_lon = 0.0 - gps_lon
          d['GPS-Longitude'] = gps_lon
        logging.debug("GPS Latitude=%s Longitude=%s",d.get('GPS-Longitude',None),d.get('GPS-Latitude',None))
        d[decoded] = gps_data
      else:
        d[decoded] = value
      logging.debug('  [%s]=[%s]',`decoded`,zapz(d[decoded]))
    context['image_exif'][name] = d
    logging.debug('EXIF(%s): END',name)
    del img

    for d in sizes :
      f = os.path.join('.%d'%(d,),name)
      if os.path.exists(f) :
        img = Image.open(f)
        context['tn%d'%(d,)] = '%dx%d' % img.size
        del img

    return context['image_sizes'][name]
  elif ImageMagick_cli :
    logging.debug("Using ImageMagick to read '%s'.",name)
    cmd = "identify -ping -format '%W %H'"
    logging.debug("++ Command was: %s",cmd)
    fp = os.popen(cmd,'r')
    o = fp.read()
    fp.close()
    logging.debug("++ Output was: %s",' '.join(o.split()))
    x, y = [int(x) for x in o.split()]
    context['image_sizes'][name] = x,y
    return context['image_sizes'][name]
  else:
    logging.fatal("Cannot process images - no backend.")
    sys.exit(2)

def copy(f_from,f_to):
  fp = open(f_to,'wb')
  fp.write(load(f_from))
  fp.close()

def intDiv(v,sfx=''):
  a, b = v
  s = str(b)
  if s.rstrip('0') == '1' :
    fmt = '%%%d.%df%%s' % (len(str(a)),len(str(b))-1)
    return fmt % (float(a)/float(b),sfx)
  return '%d/%d = %.2f%s' % (a,b,float(a)/float(b),sfx)

ExifHandler = {
  # http://www.sno.phy.queensu.ca/~phil/exiftool/TagNames/EXIF.html
  'DateTime':lambda x:str(x),
  'ExposureTime':lambda x:str(x[0])+'/'+str(x[1]),
  'FNumber':lambda x:intDiv(x),
  # http://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif/flash.html
  'Flash':lambda x:{
    0x00 : 'No Flash',
    0x01 : 'Fired',
    0x05 : 'Fired, Return not detected',
    0x07 : 'Fired, Return detected',
    0x08 : 'On, Did not fire',
    0x09 : 'On, Fired',
    0x0d : 'On, Return not detected',
    0x0f : 'On, Return detected',
    0x10  : 'Off, Did not fire',
    0x14  : 'Off, Did not fire, Return not detected',
    0x18  : 'Auto, Did not fire',
    0x19  : 'Auto, Fired',
    0x1d  : 'Auto, Fired, Return not detected',
    0x1f  : 'Auto, Fired, Return detected',
    0x20  : 'No flash function',
    0x30  : 'Off, No flash function',
    0x41  : 'Fired, Red-eye reduction',
    0x45  : 'Fired, Red-eye reduction, Return not detected',
    0x47  : 'Fired, Red-eye reduction, Return detected',
    0x49  : 'On, Red-eye reduction',
    0x4d  : 'On, Red-eye reduction, Return not detected',
    0x4f  : 'On, Red-eye reduction, Return detected',
    0x50  : 'Off, Red-eye reduction',
    0x58  : 'Auto, Did not fire, Red-eye reduction',
    0x59  : 'Auto, Fired, Red-eye reduction',
    0x5d  : 'Auto, Fired, Red-eye reduction, Return not detected',
    0x5f  : 'Auto, Fired, Red-eye reduction, Return detected',
    }.get(x,'Undefined#'+repr(x)),
  'ISOSpeedRatings':lambda x:str(x),
  'MeteringMode':lambda x:{
    0 : 'Unknown',
    1 : 'Average',
    2 : 'CenterWeightedAverage',
    3 : 'Spot',
    4 : 'MultiSpot',
    5 : 'Pattern',
    6 : 'Partial',
    255 : 'other',
    }.get(x,'Undefined#'+repr(x)),
  'ExposureProgram':lambda x:repr(x),
  'FocalLength':lambda x:intDiv(x,' mm'),
  'FileSource':lambda x:{
    '\x03' : 'Digital Still Camera',
    }.get(x,'Undefined#'+repr(x)),
  'Make':lambda x:str(x).strip(),
  'Model':lambda x:str(x).strip(),
  'Software':lambda x:repr(x),
}
KnownTags = ExifHandler.keys() ; KnownTags.sort()

def eval_perl_code(name,context):
  # this gets `eval`-ed and must return a string to be included in the
  # index html page at the top.
  # The following variables are documented:
  # $_{-version}          SVN release of the running script
  # $_{-depth}            subdir depth relative to the "top" with .gallery2
  # $_{-title}            title of the current subdir (.title contents)
  # $_{-path}             path from the dir that contains .gallery2
  if not os.path.exists(name) :
    logging.error('No PERL plugin "%s" to eval.' % (name,))
    return ''
  plvars = '$_{-version}="%s";$_{-depth}="%s";$_{-title}="%s";$_{-path}="%s";'%(
    context['version'],
    context['depth'],
    context['title'],
    context['path'],
  )
  text = ''
  try:
    cmd = "perl -e '%s' -e \"print `cat %s`;\"" % (plvars,name,)
    # logging.debug('PERL plugin will be ran as: '+cmd)
    fp = os.popen(cmd)
    time.sleep(0.4)
    text = fp.read()
    fp.close()
  except exceptions.Exception, e:
    logging.error('Error running PERL plugin "%s".'%(name,))
    logging.debug('Exception: %s'%(e,))
  return text

def run_plugin(name,context):
  if not os.path.exists(os.path.join(g2dir,name)) :
    logging.debug('No Python plugin "%s" to import (%s).' % (name,os.path.join(g2dir,name)))
    return ''
  pg2dir = os.path.abspath(g2dir)
  sys.path.insert(0,pg2dir)
  try:
    try:
      m = __import__( os.path.splitext(name)[0] )
    except exceptions.Exception, e:
      logging.error('Cannot import "%s".'%(name,))
      logging.debug('Exception: %s'%(e,))
      return ''
    if not hasattr(m,'do') :
      logging.error('Plugin module "%s" has no "do" entry.'%(name,))
      return ''
    if not callable(m.do) :
      logging.error('Plugin module "%s" has "do" entry, but it is not callable.'%(name,))
      return ''
    try:
      return m.do(context)
    except exceptions.Exception, e:
      logging.error('Error running "do" entry from plugin module "%s".'%(name,))
      logging.debug('Exception: %s'%(e,))
      return ''
  finally:
    sys.path.pop(0)

def load(fname):
  fp = open(fname)
  text = fp.read()
  fp.close()
  return text

def format_js(fname):
  if not os.path.exists(fname) :
    logging.warn('No JS file "%s"' % (fname,))
    return ''
  return '<script src="%s" type="text/javascript"></script>' % (fname,)

def format_css(fname):
  if not os.path.exists(fname) :
    logging.warn('No CSS file "%s"' % (fname,))
    return ''
  return '<link rel="stylesheet" type="text/css" href="%s" />' % (fname,)

handle_suffix = { '.js':format_js, '.css':format_css, }

def select_images(name):
  if not os.path.isfile(name) :
    if os.path.islink(name):
      if not os.path.isfile(os.readlink(name)) :
        return False # only "1" in depth...
  ext = os.path.splitext(name)[-1].lower()
  return ext in image_types

def build_context():
  context = {}
  # $_{-version}          SVN release of the running script
  # $_{-depth}            subdir depth relative to the "top" with .gallery2
  # $_{-path}             path from the dir that contains .gallery2
  context['version'] = Script
  context['depth'] = 1 # hack XXX
  context['path'] = '.' # hack XXX
  context['prereq'] = "\n".join([
    handle_suffix[os.path.splitext(f)[-1]](os.path.join(g2dir,f))
    for f in prereq
  ])
  context['all_files'] = filter(lambda x:x[0]!='.',os.listdir('.'))
  context['subdirs'] = filter(os.path.isdir,context['all_files'])
  context['pictures'] = filter(select_images,context['all_files'])
  context['pictures'].sort()
  context['picture_count'] = len(context['pictures'])
  if context['picture_count'] == 0 :
    logging.warn('There are no pictures found!')
    return
  context['first_img'] = context['pictures'][0]
  context['last_img'] = context['pictures'][-1]
  context['image_sizes'] = {}
  context['image_exif'] = {}
  context['title'] = 'Image Gallery by mkg.py'
  if os.path.exists('.title') :
    context['title'] = load('.title').strip() # % context
    logging.info("Title=[%s]"%(context['title'],))
  else:
    logging.warn('No ".title" file...')
  context['header_pl'] = eval_perl_code(os.path.join(g2dir,header_pl),context)
  context['footer_pl'] = eval_perl_code(os.path.join(g2dir,footer_pl),context)
  context['header_py'] = run_plugin(header_py,context)
  context['footer_py'] = run_plugin(footer_py,context)
  context['plugin_header'] = context['header_pl'] + context['header_py']
  context['plugin_footer'] = context['footer_pl'] + context['footer_py']
  context['curr_img'] = None
  context['curr_width'] = None
  context['curr_height'] = None
  context['map_ref'] = ''
  return context

def write_header(fp,context):
  fp.write(__HTML_header % context)

def write_footer(fp,context):
  fp.write(__HTML_footer % context)

def write_info(context):
  name = context['curr_img']
  fname = '.html/' + name + '-info.html'
  fp = open(fname,'w')
  fp.write('''<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US" xml:lang="en-US">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>%(curr_img)s</title>
<link rel="stylesheet" type="text/css" href="../.gallery2/gallery.css" />
<script src="../.gallery2/mootools.js" type="text/javascript"></script>
<script src="../.gallery2/urlparser.js" type="text/javascript"></script>
<script src="../.gallery2/infopage.js" type="text/javascript"></script>
</head>
<body>
<!-- Created by %(version)s -->
<center>
<h1>%(curr_img)s</h1>
<table class="ipage">
<tr><td><img class="thumbnail" src="../.160/%(curr_img)s" alt="%(curr_img)s" /></td> <td><table class="infotable">
''' % context)
  d = context['image_exif'][name]
  for k in KnownTags:
    if k in d :
      if k in ExifHandler :
        o = ExifHandler[k](d[k])
      else:
        o = repr(d[k])
      fp.write("<tr><td>%s:</td><td>%s</td></tr>\n"%(k, o))
  if ('GPS-Latitude' in d) and ('GPS-Longitude' in d) :
    fp.write("<tr><td claspan=\"2\">%s</td></tr>\n" % (context['map_ref'],))
    fp.write("<tr><td>Latitude:</td><td>%s</td></tr>\n"%(d['GPS-Latitude'],))
    fp.write("<tr><td>Longitude:</td><td>%s</td></tr>\n"%(d['GPS-Longitude'],))
  fp.write('''</table>
</td></tr></table><a class="conceal" href="../index.html">Index</a>
</center>
</body>
</html>
''')
  fp.close()
  pass

def write_slide(context):
  name = context['curr_img']
  fname = '.html/' + name + '-slide.html'
  fp = open(fname,'w')
  fp.write('''<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US" xml:lang="en-US">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>%(curr_img)s</title>
<meta http-equiv="Refresh" content="3; url=%(next_img)s-slide.html" />
<link rel="stylesheet" type="text/css" href="../.gallery2/gallery.css" />
</head>
<body bgcolor="#808080">
<!-- Created by %(version)s -->
<h1>%(curr_img)s</h1>
<table class="navi">
<td><a href="../index.html">Index</a></td>
<td><a href="IMG_2976.JPG-slide.html">&lt;&lt;Prev</a></td>
<td><a href="%(curr_img)s-static.html">Stop!</a></td>
<td><a href="IMG_2978.JPG-slide.html">Next&gt;&gt;</a></td>
<td class="title">%(curr_img)s</td>
</tr></table>
<center><table class="picframe"><tr><td><img class="standalone" src="../.640/%(curr_img)s" alt="%(curr_img)s" /></td></tr></table></center>
</body>
</html>
''' % context)
  fp.close()
  pass

def write_static(context):
  name = context['curr_img']
  fname = '.html/' + name + '-static.html'
  fp = open(fname,'w')
  fp.write('''<!DOCTYPE html
    PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US" xml:lang="en-US">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>%(curr_img)s</title>
<link rel="stylesheet" type="text/css" href="../.gallery2/gallery.css" />
</head>
<body bgcolor="#808080">
<!-- Created by %(version)s -->
<h1>%(curr_img)s</h1>
<table class="navi">
<td><a href="../index.html">Index</a></td>
<td><a href="%(prev_img)s-static.html">&lt;&lt;Prev</a></td>
<td><a href="%(curr_img)s-slide.html">Play!</a></td>
<td><a href="%(next_img)s-static.html">Next&gt;&gt;</a></td>
<td class="title">%(curr_img)s</td>
</tr></table>
<center><table class="picframe"><tr><td><img class="standalone" src="../.640/%(curr_img)s" alt="%(curr_img)s" /></td></tr></table></center>
</body>
</html>
''' % context)
  fp.close()
  pass

def write_body(fp,context):
  i = 0
  for name in context['pictures'] :
    logging.info('...handling <%s>...',name)
    context['prev_img'] = ''
    context['next_img'] = ''
    if i :
      context['prev_img'] = context['curr_img']
    i += 1
    if i < len(context['pictures']) :
      context['next_img'] = context['pictures'][i]
    if sys.stderr.isatty() :
      sys.stderr.write("\r%d/%d\r"%(i,context['picture_count']))
    context['curr_img'] = name
    context['curr_width'], context['curr_height'] = image_size(name,context)
    exif = context['image_exif'][name]
    logging.debug("Image size (%s): %dx%d",name,context['curr_width'], context['curr_height'])
    #if imghdr.what(name) != 'jpeg' :
    #  logging.error("Unsupported file type '%s' for '%s'.",imghdr.what(name),name)
    if ExifTran_cli :
      rotate_to_normal(name)
    for size in sizes :
      xname = '.%s/%s' % (size,name)
      if not os.path.exists(xname) :
        logging.debug("No scale '%s' for '%s'.",size,name)
        resize_image(name,size,context)
    context['map_ref'] = ''
    #print repr(exif)
    #print repr(exif.get('GPSInfo',None))
    if 'GPSInfo' in exif :
      lat = exif.get('GPS-Latitude',None)
      lon = exif.get('GPS-Longitude',None)
      if lat and lon :
        context['map_ref'] = "\n ".join(('<a class="geoloc" title="%(lat)s,%(lon)s" href="http://maps.google.com/?q=%(lat)s,%(lon)s&amp;ll=%(lat)s,%(lon)s"><div class="geoloc"></div></a>' % {
          'lat':lat, 'lon':lon,
        }).split())
    fp.write(__HTML_body % context)
    write_info(context)
    write_slide(context)
    write_static(context)


def rotate_to_normal(name):
  if RefreshOnly :
    return
  if ExifTran_cli :
    try:
      cmd = 'exiftran -a -i -p "%s" 2>&1' % (name,)
      logging.debug("Running '%s'.",cmd)
      fp = os.popen(cmd,'r')
      # time.sleep(0.3)
      text = fp.read()
      fp.close()
    except exceptions.Exception, e:
      logging.error('ExifTran CLI error.')
      logging.debug('Exception: %s'%(e,))
    else:
      logging.debug("Exiftran output: '%s'.",' '.join(text.strip().split()))
  else:
    logging.debug("Cannot rotate image '%s'.",name)

def check_ExifTran_cli():
  global ExifTran_cli
  try:
    fp = os.popen('exiftran 2>&1','r')
    time.sleep(0.3)
    text = fp.read()
    fp.close()
    ExifTran_cli = 'more info' in text
  except exceptions.Exception, e:
    logging.debug('No ExifTran CLI available.')
    logging.debug('Exception: %s'%(e,))
  else:
    logging.debug('ExifTran CLI available.')

def check_ImageMagick_cli():
  global ImageMagick_cli
  try:
    fp = os.popen('mogrify -version','r')
    time.sleep(0.3)
    text = fp.read()
    fp.close()
    ImageMagick_cli = 'ImageMagick' in text
  except exceptions.Exception, e:
    logging.debug('No ImageMagick CLI available.')
    logging.debug('Exception: %s'%(e,))
  else:
    logging.debug('ImageMagick CLI available.')

def check_PIL():
  if PIL_ok :
    logging.debug('PIL available.')
  else:
    logging.debug('No PIL available.')

def check_PyExiv2():
  if PyExiv2_ok :
    logging.debug('PyExiv2 available.')
  else:
    logging.debug('No PyExiv2 available.')

def check_GExiv2():
  if gExiv2_ok :
    logging.debug('GExiv2 available.')
  else:
    logging.debug('No GExiv2 available.')

def handle( fname ):
  print fname

def main():
  global RefreshOnly
  try:
    logging.root.setLevel(logging.INFO)
    try:
      opts, args = getopt.getopt(
        sys.argv[1:],
	'?hds:f',
	('help','debug','setup=','refresh')
      )
    except getopt.error, why:
      print >>sys.stderr, sys.argv[0],':',why
      return 1
    else:
      for o,v in opts :
        if o in ('-h','-?','--help'):
	  print '-d, --debug -- be verbose'
          print '-s, --setup=<template-dir> -- setup using template'
          print '-f, --refresh -- rebuild HTMLs only'
	  return 0
        elif o in ('-d','--debug'):
          logging.root.setLevel(logging.DEBUG)
        elif o in ('-f','--refresh'):
          RefreshOnly = True
        elif o in ('-s','--setup'):
          logging.debug('Setup requested. Template: "%s".',v)
          if not os.path.isdir(v) :
            logging.fatal("Cannot setup: '%s' is not a directory",v)
            return 1
          if os.path.basename(v) != g2dir :
            v = os.path.join(v,g2dir)
          if not os.path.isdir(v) :
            logging.fatal("Cannot setup: no '%s' directory",v)
            return 1
          track = []
          while os.path.islink(v) :
            if v in track :
              logging.fatal("Symlink loop at '%s' detected.",v)
              return 1
            track.append(v[:])
            v = os.readlink(v)
          else:
            logging.debug("Resolved to '%s'.",v)
          os.symlink(v,g2dir)
          logging.info("Setup has been performed.")
          return 0
        pass
    for arg in args :
      handle( arg )

    logging.debug('Checking environment...')
    if not os.path.exists(g2dir) :
      logging.error("Cannot run - no mkgallery2 backend '%s'.",g2dir)
      return 1
    if not os.path.isdir(g2dir) :
      if os.path.islink(g2dir) :
        if not os.path.isdir(os.readlink(g2dir)) :
          logging.error("Cannot run - no usable mkgallery2 backend '%s' - bad symlink.",g2dir)
          return 1
        logging.debug("mkgallery2 backend '%s' symlinked to '%s'.",g2dir,os.readlink(g2dir))
      else:
        logging.error("Cannot run - no usable mkgallery2 backend '%s'.",g2dir)
        return 1

    check_ExifTran_cli()
    check_ImageMagick_cli()
    check_PIL()
    check_PyExiv2()
    check_GExiv2()

    for d in subdirs :
      if os.path.exists(d) :
        if not os.path.isdir(d) :
          logging.error("Bad entry '%s' -- cannot use.",d)
          return 1
      else:
        try:
          os.mkdir(d)
        except exceptions.Exception, e:
          logging.error("Cannot mkdir(%s).",d)
          logging.debug('Exception: %s'%(e,))
          return 1

    logging.debug('Building context...')
    context = build_context()
    if context is None :
      return 0

    logging.debug('Writing output to "%s"...',output)
    fp = open(output,'w')
    write_header(fp,context)
    write_body(fp,context)
    write_footer(fp,context)
    fp.close()
    logging.debug('Done.')
    return 0
  finally:
    pass

def __fix_io_encoding(last_resort_default='UTF-8'):
  import sys
  if [x for x in (sys.stdin,sys.stdout,sys.stderr) if x.encoding is None] :
    import os
    defEnc = None
    if defEnc is None :
      try:
        import locale
        defEnc = locale.getpreferredencoding()
      except: defEnc = None
    if defEnc is None :
      try: defEnc = sys.getfilesystemencoding()
      except: defEnc = None
    if defEnc is None :
      try: defEnc = sys.stdin.encoding
      except: defEnc = None
    if defEnc is None : defEnc = last_resort_default
    os.environ['PYTHONIOENCODING'] = os.environ.get("PYTHONIOENCODING",defEnc)
    os.execvpe(sys.argv[0],sys.argv,os.environ)

if __name__=='__main__' :
  __fix_io_encoding()
  del __fix_io_encoding
  sys.exit( main() )
# vim:ai:sts=2:et
# EOF #
