

import exifread
# Open image file for reading (binary mode)
f = open(path_name, 'rb')

# Return Exif tags
tags = exifread.process_file(f)

for k, v in tags.iteritems():
   print k
   print v
