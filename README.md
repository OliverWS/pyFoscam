pyFoscam
========

Simple python library for controlling Foscam FI9826W

Example
===
'''Python
from foscam import *

mycam = Foscam("http://10.0.1.4:88",user="admin",password="***REMOVED***")

mycam.pan("left",0.5)

mycam.pan("right",0.5)

mycam.pan("up",0.5)

mycam.pan("down",0.5)

mycam.zoom("in",0.5)

mycam.zoom("out",0.5)

mycam.schedule
Out[490]: [{'day': 'monday', 'end': '6:30', 'start': '2:30'}]

s = mycam.schedule

s.append({"day":"sunday","start":"22:00","end":"23:30"})

mycam.schedule = s

mycam.schedule
Out[494]: 
[{'day': 'monday', 'end': '6:30', 'start': '2:30'},
 {'day': 'sunday', 'end': '23:30', 'start': '22:00'}]
'''

