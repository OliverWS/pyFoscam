'''
Name:     pyFoscam
Source:   https://github.com/oliverws/pyFoscam
Feedback: https://github.com/oliverws/pyFoscam/issues
Author: Oliver Wilder-Smith

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>
'''

import requests
import xmltodict
from threading import Timer

CGI_PATH = "/cgi-bin/CGIProxy.fcgi"
PTZ = {
	"up":"ptzMoveUp",
	"down":"ptzMoveDown",
	"left":"ptzMoveLeft",
	"right":"ptzMoveRight",
	"upright":"ptzMoveTopRight",
	"upleft":"ptzMoveTopLeft",
	"downright":"ptzMoveDownRight",
	"downleft":"ptzMoveDownLeft",
	"stop":"ptzStopRun"
}
ZOOM = {
	"in":"zoomIn",
	"out":"zoomOut",
	"stop":"zoomStop"
}

IR_MODE = ["auto","manual","schedule"]
DAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
def binary(num):
	'''Custom binary string formatter for use in parsing schedule representation used by Foscam'''
	bs = bin(num)[2:].rjust(48,'0')
	return "".join(reversed(bs))

class Foscam:
	def __init__(self,url,user="admin",password=""):
		'''The Foscam class constructor expects:
		\t*url: a url + port combo, such as 'http://192.168.0.100:8888'
		\t*user: the username for the camera (must be an admin to control some settings)
		\t*password: the password for the specified user
		'''
		self.url = url
		self.user = user
		self.password = password
		self.scheduleEnabled = True
		self.recordLevel = 4
		self.spaceFullMode = 0
		self.isEnableAudio = True
		self.default_ir_mode = self.ir_mode

	def IR_ON(self):
		'''Sets the camera's IR LEDs on, and switches to IR mode'''
		self.ir_mode = "manual"
		self.request({"cmd":"openInfraLed"})
	
	def IR_OFF(self):
		'''Sets the camera's IR LEDs off, and reverts to default IR mode'''
		self.request({"cmd":"closeInfraLed"})
		self.ir_mode = self.default_ir_mode

	@property
	def ir_mode(self):
	    resp = self.request({"cmd":"getInfraLedConfig"})
	    mode = IR_MODE[int(xmltodict.parse(resp.text)["CGI_Result"]["mode"])]
	    return mode

	@ir_mode.setter
	def ir_mode(self, value):
	    self.request({"cmd":"setInfraLedConfig","mode":IR_MODE.index(value.lower())})
	    self.default_ir_mode = value
	
	def pan(self,direction,duration=None):
		'''Pan camera in specified direction. Optionally specify a duration for which to pan (otherwise it will pan until 'stop' is called or end of range is reached)
		The following are valid directions:
			"up"
			"down"
			"left"
			"right"
			"upright" (Diagonally up and to the right)
			"upleft" (Diagonally up and to the left)
			"downright" (Diagonally down and to the right)
			"downleft" (Diagonally down and to the left)
			"stop" (Freeze camera in current position)
		'''
		if direction.lower() in PTZ:
			self.request({"cmd":PTZ[direction.lower()]})
			if duration != None:
				Timer(duration, self.stop_pan).start()
		else:
			return False
	
	def stop_pan(self):
		self.request({"cmd":PTZ["stop"]})

	def stop_zoom(self):
		self.request({"cmd":ZOOM["stop"]})
	
	def zoom(self,direction, duration=None):
		'''Zoom camera in specified direction. Optionally specify a duration for which to zoom (otherwise it will pan until 'stop' is called or end of range is reached)
		The following are valid zoom:
			"in"
			"out"
			"stop" (Freeze camera in current zoom level)
		'''
		if direction.lower() in ZOOM:
			self.request({"cmd":ZOOM[direction.lower()]})
			if duration != None:
				Timer(duration, self.stop_zoom).start()
		else:
			return False
	@property
	def schedule(self):
		'''The camera's recording schedule is represented as a set of dict objects representing a recording segment,
		each of which has a start, end, and day (day of the week). Foscam currently only supports starting or ending recordings
		on the hour or half hour, so times are rounded to the nearest half hour.
		Example: 
			mycam.schedule = [
				{"day":"monday", "start":"09:30", "end":"14:00"},
				{"day":"wednesday", "start":"11:00", "end":"16:00"}
			]
		'''

		return self.getSchedule()
	@schedule.setter
	def schedule(self, value):
	    self.setSchedule(value)
	
	def getSchedule(self):
		'''Reads the current schedule from the camera, converting to a set of discrete segments
		The camera's recording schedule is represented as a set of dict objects representing a recording segment,
		each of which has a start, end, and day (day of the week). Foscam currently only supports starting or ending recordings
		on the hour or half hour, so times are rounded to the nearest half hour.
		Example: 
			In[400]: mycam.schedule
			Out[400]:
			[
				{"day":"monday", "start":"09:30", "end":"14:00"},
				{"day":"wednesday", "start":"11:00", "end":"16:00"}
			]
		'''

		resp = self.request({"cmd":"getScheduleRecordConfig"})
		schedule_raw = xmltodict.parse(resp.text)["CGI_Result"]
		days = [x for x in schedule_raw.items() if "schedule" in x[0]]
		segments = []
		for d in days:
			day = DAYS[int(d[0][-1])]
			bitstring = binary(int(d[1])) # Binary representation, with each binary digit representing a 30 minute block
			i = 0
			while i < len(bitstring):
				if bitstring[i] == '1':
					#A '1' indicates that recording will begin in this block
					segment = {"day":day}
					start = str(int(i)/2) + ":" + ("00" if ((i%2)==0) else "30")
					segment["start"] = start
					#Now we iterate through till we find a '0', indicating the end of the block
					while (i < len(bitstring)) and  (bitstring[i] == '1'):
						i = i + 1
					segment["end"] = str(int(i)/2) + ":" + ("00" if (((i)%2)==0) else "30") # Note that Foscam treats ending blocks as inclusive
					segments.append(segment)
					continue
				else:
					i = i + 1
		return segments
	def setSchedule(self,segments, clearMissing=True):
		'''Reads the current schedule from the camera, converting to a set of discrete segments
		The camera's recording schedule is represented as a set of dict objects representing a recording segment,
		each of which has a start, end, and day (day of the week). Foscam currently only supports starting or ending recordings
		on the hour or half hour, so times are rounded to the nearest half hour.
		The optional parameter, clearMissing, controls whether to retain existing scheduled recordings not overwritten by the current set (default is no). 
		***The recommended way to manage recordings is using the Foscam.schedule property, rather than calling the getter or setter directly
		Example: 
			In[400]: mycam.schedule =
			[
				{"day":"monday", "start":"09:30", "end":"14:00"},
				{"day":"wednesday", "start":"11:00", "end":"16:00"}
			]
		'''
		# For reasons that are beyond me Foscam uses a strange binary representation, converted to decimal, which is 48 bits long, with each bit representing 30 mins in a day
		# segment is dict with {'day':'monday', 'start':'11:30','end':'15:30'}
		if clearMissing:
			#Start with a blank slate, no recordings
			params = {
				"schedule0":0,
				"schedule1":0,
				"schedule2":0,
				"schedule3":0,
				"schedule4":0,
				"schedule5":0,
				"schedule6":0
			}
		else:
			#Start with existing schedules, overwrite only where specified
			params = self.getSchedule()
		params["cmd"]="setScheduleRecordConfig"
		params["isEnable"] = int(self.scheduleEnabled)
		params["recordLevel"] = int(self.recordLevel)
		params["spaceFullMode"] = int(self.spaceFullMode)
		params["isEnableAudio"] = int(self.isEnableAudio)
		
		for s in segments:
			start = s["start"]
			end = s["end"]
			day = s["day"]
			start_offset = int(start.split(":")[0])*2 + int(int(start.split(":")[1]) >= 30)
			end_offset = int(end.split(":")[0])*2 + int(int(end.split(":")[1]) >= 30)
			bit_mask = 0
			for i in range(start_offset,end_offset):
				bit_mask += (1 << i)
			params["schedule%d"%(DAYS.index(day))] = bit_mask
		return self.request(params)



	def request(self,params={}):
		'''Build request with user and password params added'''
		params["usr"] = self.user
		params["pwd"] = self.password
		r = requests.get(self.url + CGI_PATH, params=params)
		return r